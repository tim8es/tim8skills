#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Characterization tests for obsidian-kanban scripts.

Covers key invariants identified in eng.H1 (no test suite → blind refactoring):
  - parse_board / emit_board round-trip
  - build_tag_line / parse_tag_line round-trip
  - stamp_done idempotency
  - normalize_column CLI-safe aliases

Run with pytest (from workspace root):
    python -m pytest .agents/skills/obsidian-kanban/scripts/test_kanban.py -v

Fallback (stdlib only, no pytest install required):
    python .agents/skills/obsidian-kanban/scripts/test_kanban.py
"""
import sys
import tempfile
import unittest
from pathlib import Path

# Add scripts/ to sys.path so kanban_utils, move_card, lint_board etc. are importable
# regardless of CWD when pytest discovers this file.
_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import kanban_utils as ku
import hooks
import resume
import role_prompt
import spec_brief
import loop_metrics
import datetime as dt
import check_reminders as cr
import lint_board as lb
from move_card import (
    stamp_done,
    sync_spec_status,
    transition_actor,
    _substitute_script_prefix,
    _PLACEHOLDER,
    _CANONICAL,
)

# ---------------------------------------------------------------------------
# Sample board text — used for round-trip tests
# ---------------------------------------------------------------------------
_SAMPLE_BOARD = (
    "---\n\nkanban-plugin: board\n\n---\n\n"
    "## BACKLOG\n\n"
    "- [ ] [[task-alpha|Task Alpha: example]]\n"
    "\t➕ 2026-06-01 \U0001f6eb 2026-06-01 ⏳ 1h\n\n"
    "## ICEBOX\n\n"
    "## TODO\n\n"
    "- [ ] [[task-beta|Task Beta: medium priority]]\n"
    "\t➕ 2026-06-02 \U0001f7e8\n\n"
    "## IN PROGRESS\n\n"
    "## BLOCKED\n\n"
    "## TESTING\n\n"
    "## IN REVIEW\n\n"
    "## REJECTED\n\n"
    "## REWORK\n\n"
    "## DONE\n\n"
    "- [x] [[task-gamma|Task Gamma: done]]\n"
    "\t➕ 2026-06-03 \U0001f6eb 2026-06-03 ✅ 2026-06-10 22:00\n\n"
    "\n"
    "%% kanban:settings\n"
    '{\"kanban-plugin\":\"board\",\"list-collapse\":'
    "[false,false,false,false,false,false,false,false,false,false]}\n"
    "%%\n"
)


# ---------------------------------------------------------------------------
# Test: parse_board / emit_board round-trip
# ---------------------------------------------------------------------------

class TestParseEmitRoundTrip(unittest.TestCase):
    """parse_board(emit_board(parse_board(text))) == parse_board(text)."""

    def test_columns_survive_roundtrip(self):
        cols1, settings1 = ku.parse_board(_SAMPLE_BOARD)
        emitted = ku.emit_board(cols1, settings1)
        cols2, settings2 = ku.parse_board(emitted)
        self.assertEqual(cols1, cols2, "columns differ after round-trip")
        self.assertEqual(settings1, settings2, "settings differ after round-trip")

    def test_all_canonical_columns_present(self):
        cols, _ = ku.parse_board(_SAMPLE_BOARD)
        for col in ku.COLUMN_ORDER:
            self.assertIn(col, cols, f"column {col!r} missing after parse_board")

    def test_card_count_preserved(self):
        cols1, settings1 = ku.parse_board(_SAMPLE_BOARD)
        emitted = ku.emit_board(cols1, settings1)
        cols2, _ = ku.parse_board(emitted)
        for col in ku.COLUMN_ORDER:
            self.assertEqual(len(cols1[col]), len(cols2[col]),
                             f"card count in {col!r} changed after round-trip")


# ---------------------------------------------------------------------------
# Test: build_tag_line / parse_tag_line round-trip
# ---------------------------------------------------------------------------

class TestTagRoundTrip(unittest.TestCase):
    """build_tag_line(parse_tag_line(line)) == line for canonical tag lines."""

    def _rt(self, line):
        return ku.build_tag_line(ku.parse_tag_line(line))

    def test_full_tag_line_all_fields(self):
        # §7 canonical order: ➕ 🛫 📅 ⏳ priority 🔁 ✅
        line = "\t➕ 2026-06-01 \U0001f6eb 2026-06-02 \U0001f4c5 2026-06-30 ⏳ 30m \U0001f7e5 \U0001f501 ✅ 2026-06-25"
        self.assertEqual(self._rt(line), line)

    def test_created_only(self):
        line = "\t➕ 2026-06-01"
        self.assertEqual(self._rt(line), line)

    def test_priority_medium(self):
        line = "\t➕ 2026-06-01 \U0001f7e8"
        self.assertEqual(self._rt(line), line)

    def test_priority_low(self):
        line = "\t➕ 2026-06-01 \U0001f7e9"
        self.assertEqual(self._rt(line), line)

    def test_done_with_time(self):
        line = "\t➕ 2026-06-01 \U0001f6eb 2026-06-01 ✅ 2026-06-10 22:00"
        self.assertEqual(self._rt(line), line)

    def test_empty_dict_gives_empty_string(self):
        self.assertEqual(ku.build_tag_line({}), "")


# ---------------------------------------------------------------------------
# Test: task spec scaffold quality
# ---------------------------------------------------------------------------

class TestTaskSpecScaffold(unittest.TestCase):
    """New task specs should give reviewers concrete checks by default."""

    def test_task_review_checklist_has_quality_baseline(self):
        text = ku.build_spec_text("task", "task-alpha", "DEV: Task Alpha", "project-alpha")
        review = text.split("## Review Checklist\n", 1)[1].split("\n## Dependencies", 1)[0]
        items = [line for line in review.splitlines() if line.startswith("- [ ] ")]
        self.assertGreaterEqual(len(items), 4)
        self.assertIn("- [ ] Artifact or code exists at the expected path", review)
        self.assertIn("- [ ] All DoD items are completed", review)
        self.assertIn("- [ ] No regressions in adjacent functionality", review)
        self.assertIn("- [ ] Documentation or task notes are updated when applicable", review)
        self.assertNotIn("- [ ] All DoD items completed", review)


# ---------------------------------------------------------------------------
# Test: stamp_done idempotency
# ---------------------------------------------------------------------------

class TestStampDoneIdempotent(unittest.TestCase):
    """stamp_done(stamp_done(block)) == stamp_done(block) — no duplicate ✅."""

    @staticmethod
    def _tag_line(block):
        return next((l for l in block if l.startswith("\t")), "")

    def test_single_call_adds_done_stamp(self):
        block = ["- [x] [[task-x|Task X]]", "\t➕ 2026-06-01"]
        once = stamp_done(block)
        tag = self._tag_line(once)
        self.assertIn("✅", tag)
        self.assertEqual(tag.count("✅"), 1)

    def test_double_call_no_duplicate(self):
        block = ["- [x] [[task-x|Task X]]", "\t➕ 2026-06-01"]
        once = stamp_done(block)
        twice = stamp_done(once)
        tag_once = self._tag_line(once)
        tag_twice = self._tag_line(twice)
        self.assertEqual(tag_twice.count("✅"), 1,
                         f"duplicate ✅ after double stamp_done: {tag_twice!r}")
        self.assertEqual(tag_once, tag_twice,
                         f"stamp_done not idempotent: {tag_once!r} != {tag_twice!r}")

    def test_block_without_tag_line(self):
        block = ["- [x] [[task-y|Task Y]]"]
        once = stamp_done(block)
        twice = stamp_done(once)
        tag_once = self._tag_line(once)
        tag_twice = self._tag_line(twice)
        self.assertIn("✅", tag_once)
        self.assertEqual(tag_once.count("✅"), 1)
        self.assertEqual(tag_once, tag_twice)

    def test_already_stamped_block_unchanged(self):
        block = ["- [x] [[task-z|Task Z]]", "\t➕ 2026-06-01 ✅ 2026-06-10 14:30"]
        once = stamp_done(block)
        tag = self._tag_line(once)
        # must not append another ✅ on pre-stamped card
        self.assertEqual(tag.count("✅"), 1,
                         f"stamp_done added ✅ to already-stamped card: {tag!r}")


class TestStartStampTiming(unittest.TestCase):
    """Start tags are created when work starts, not when a card becomes ready."""

    @staticmethod
    def _workspace(td):
        root = Path(td)
        tasks = root / "tasks"
        specs = tasks / "specs"
        specs.mkdir(parents=True)
        (tasks / "demo.md").write_text(_MINIMAL_BOARD, encoding="utf-8")
        (specs / "task-alpha.md").write_text(
            "---\n"
            "flowId: demo/task/task-alpha\n"
            "itemType: task\n"
            "status: backlog\n"
            "parentId: null\n"
            "step: null\n"
            "owner: user\n"
            "priority: medium\n"
            "createdAt: 2026-06-01 10:00\n"
            "updatedAt: 2026-06-01 10:00\n"
            "reminder: null\n"
            "startedAt: null\n"
            "testingAt: null\n"
            "reviewAt: null\n"
            "doneAt: null\n"
            "dependsOn: []\n"
            "blocks: []\n"
            "---\n\n"
            "# Task Alpha\n\n"
            "## Definition of Done (DoD)\n- [ ] Done\n\n"
            "## Changelog\n\n"
            "## Comments\n",
            encoding="utf-8",
        )
        return root, tasks

    @staticmethod
    def _move(root, slug, column):
        import move_card as mc
        old_argv = sys.argv[:]
        try:
            sys.argv = ["move_card.py", str(root), slug, column, "--board", "demo.md"]
            return mc.main()
        finally:
            sys.argv = old_argv

    @staticmethod
    def _tags_start(root, slug):
        import set_card_tags as tags
        old_argv = sys.argv[:]
        try:
            sys.argv = ["set_card_tags.py", str(root), slug, "--start", "today", "--board", "demo.md"]
            return tags.main()
        finally:
            sys.argv = old_argv

    def test_todo_transition_does_not_stamp_start(self):
        # before_move now gates BACKLOG->TODO on startedAt already being set
        # (analyst stamps it on entry, see agents/analyst.md) — the analyst's
        # own tags --start call is the one and only source of the 🛫 stamp;
        # the TODO move itself must not add a second one.
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            self.assertEqual(self._tags_start(root, "task-alpha"), 0)
            self.assertEqual(self._move(root, "task-alpha", "TODO"), 0)
            board = (tasks / "demo.md").read_text(encoding="utf-8")
            self.assertIn("[[task-alpha|Task Alpha]]", board)
            self.assertEqual(board.count("🛫"), 1)

    def test_in_progress_transition_does_not_infer_start(self):
        # Same gate as above applies before TODO is reachable; this test's
        # remaining concern is that the IN PROGRESS transition doesn't
        # re-infer/re-stamp startedAt or duplicate the 🛫 tag once it's set.
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            self.assertEqual(self._tags_start(root, "task-alpha"), 0)
            started_line = next(
                l for l in (tasks / "specs" / "task-alpha.md").read_text(encoding="utf-8").splitlines()
                if l.startswith("startedAt:")
            )
            self.assertEqual(self._move(root, "task-alpha", "TODO"), 0)
            # TODO -> IN PROGRESS is gated on a planner comment (see
            # agents/planner.md / hooks.before_move) — unrelated to start-stamp
            # timing, just a precondition to reach the transition under test.
            spec_path = tasks / "specs" / "task-alpha.md"
            spec_path.write_text(
                spec_path.read_text(encoding="utf-8").replace(
                    "## Comments\n",
                    "## Comments\n2026-07-05 00:00:00 | planner | estimate ok, no blockers\n",
                ),
                encoding="utf-8",
            )
            self.assertEqual(self._move(root, "task-alpha", "IN_PROGRESS"), 0)
            board = (tasks / "demo.md").read_text(encoding="utf-8")
            spec = (tasks / "specs" / "task-alpha.md").read_text(encoding="utf-8")
            self.assertEqual(board.count("🛫"), 1)
            self.assertIn(started_line, spec)

    def test_tags_start_updates_board_and_started_at_once(self):
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            self.assertEqual(self._tags_start(root, "task-alpha"), 0)
            self.assertEqual(self._tags_start(root, "task-alpha"), 0)
            board = (tasks / "demo.md").read_text(encoding="utf-8")
            spec = (tasks / "specs" / "task-alpha.md").read_text(encoding="utf-8")
            self.assertEqual(board.count("🛫"), 1)
            self.assertNotIn("startedAt: null", spec)
            self.assertEqual(spec.count("startedAt:"), 1)


# ---------------------------------------------------------------------------
# Test: normalize_column aliases
# ---------------------------------------------------------------------------

class TestNormalizeColumnAliases(unittest.TestCase):
    """normalize_column resolves CLI-safe aliases to canonical board column names."""

    def test_in_progress_underscore(self):
        self.assertEqual(ku.normalize_column("IN_PROGRESS"), "IN PROGRESS")

    def test_in_progress_hyphen(self):
        self.assertEqual(ku.normalize_column("IN-PROGRESS"), "IN PROGRESS")

    def test_in_review_no_sep(self):
        self.assertEqual(ku.normalize_column("INREVIEW"), "IN REVIEW")

    def test_in_review_underscore(self):
        self.assertEqual(ku.normalize_column("IN_REVIEW"), "IN REVIEW")

    def test_in_review_hyphen(self):
        self.assertEqual(ku.normalize_column("IN-REVIEW"), "IN REVIEW")

    def test_canonical_names_pass_through(self):
        for col in ku.COLUMN_ORDER:
            self.assertEqual(ku.normalize_column(col), col,
                             f"canonical column {col!r} should pass through unchanged")

    def test_lowercase_aliases_resolved(self):
        self.assertEqual(ku.normalize_column("in_progress"), "IN PROGRESS")
        self.assertEqual(ku.normalize_column("in_review"), "IN REVIEW")

    def test_lowercase_canonical_uppercased(self):
        self.assertEqual(ku.normalize_column("done"), "DONE")
        self.assertEqual(ku.normalize_column("backlog"), "BACKLOG")
        self.assertEqual(ku.normalize_column("todo"), "TODO")


# ---------------------------------------------------------------------------
# Test: _substitute_script_prefix [eng.F2]
# ---------------------------------------------------------------------------

class TestSubstituteScriptPrefix(unittest.TestCase):
    """_substitute_script_prefix replaces placeholders in canonical order."""

    def test_placeholder_replaced(self):
        text = f"python {_PLACEHOLDER}kanban.py move"
        result = _substitute_script_prefix(text, ".agents/skills/obsidian-kanban/scripts/")
        self.assertIn(".agents/skills/obsidian-kanban/scripts/kanban.py", result)
        self.assertNotIn(_PLACEHOLDER, result)

    def test_canonical_legacy_literal_replaced(self):
        # Role files may contain the canonical literal; it must be replaced too.
        # Use a custom prefix that doesn't contain _CANONICAL as a substring
        # (e.g. "custom-scripts/" not ".agents/skills/obsidian-kanban/scripts/")
        text = f"python {_CANONICAL}kanban.py check"
        custom = "custom-scripts/"
        result = _substitute_script_prefix(text, custom)
        self.assertIn(custom + "kanban.py", result)
        self.assertNotIn(_CANONICAL, result)

    def test_order_safe_no_double_prefix(self):
        # Canonical literal + placeholder in same text must not produce double prefix.
        # If order were reversed, CANONICAL → custom, then PLACEHOLDER → custom would
        # re-match the trailing part of the first substitution → "custom/custom/..."
        text = f"{_CANONICAL}move ; {_PLACEHOLDER}check"
        custom = "skills/obsidian-kanban/scripts/"
        result = _substitute_script_prefix(text, custom)
        self.assertNotIn(custom + custom, result, "double prefix detected — order bug")
        self.assertEqual(result.count(custom), 2)


# ---------------------------------------------------------------------------
# Test: owner is task author, not current executor
# ---------------------------------------------------------------------------

class TestOwnerAuthorInvariant(unittest.TestCase):
    """move_card status sync must not rewrite owner on transitions."""

    def test_sync_spec_status_preserves_owner(self):
        with tempfile.TemporaryDirectory() as td:
            specs = Path(td)
            spec = specs / "task-owner.md"
            spec.write_text(
                "---\n"
                "flowId: demo/task/task-owner\n"
                "itemType: task\n"
                "status: backlog\n"
                "parentId: null\n"
                "step: null\n"
                "owner: user\n"
                "priority: medium\n"
                "createdAt: 2026-06-27 00:00:00\n"
                "updatedAt: 2026-06-27 00:00:00\n"
                "reminder: null\n"
                "startedAt: null\n"
                "testingAt: null\n"
                "reviewAt: null\n"
                "doneAt: null\n"
                "dependsOn: []\n"
                "blocks: []\n"
                "---\n\n"
                "# Task\n\n"
                "## Changelog\n\n"
                "## Comments\n",
                encoding="utf-8",
            )

            changed = sync_spec_status(
                specs,
                "task-owner",
                "in-progress",
                dry=False,
                src_col="BACKLOG",
                dst_col="IN PROGRESS",
                card_title="DEV: Task",
            )

            self.assertTrue(changed)
            text = spec.read_text(encoding="utf-8")
            self.assertIn("status: in-progress", text)
            self.assertIn("owner: user", text)
            self.assertNotIn("owner: developer", text)


class TestTransitionChangelogActor(unittest.TestCase):
    """Move-generated changelog entries should name the role that moved the card."""

    @staticmethod
    def _spec(specs: Path, slug: str):
        spec = specs / f"{slug}.md"
        spec.write_text(
            "---\n"
            f"flowId: demo/task/{slug}\n"
            "itemType: task\n"
            "status: ready\n"
            "parentId: null\n"
            "step: null\n"
            "owner: user\n"
            "priority: medium\n"
            "createdAt: 2026-06-27 00:00:00\n"
            "updatedAt: 2026-06-27 00:00:00\n"
            "reminder: null\n"
            "startedAt: 2026-06-27 00:00:00\n"
            "testingAt: null\n"
            "reviewAt: null\n"
            "doneAt: null\n"
            "dependsOn: []\n"
            "blocks: []\n"
            "---\n\n"
            "# Task\n\n"
            "## Changelog\n\n"
            "## Comments\n",
            encoding="utf-8",
        )
        return spec

    def test_transition_actor_uses_source_column_role(self):
        self.assertEqual(transition_actor("TODO", "DEV: Task"), "planner")
        self.assertEqual(transition_actor("IN PROGRESS", "DEV: Task"), "developer")

    def test_sync_spec_status_writes_planner_for_todo_to_in_progress(self):
        with tempfile.TemporaryDirectory() as td:
            specs = Path(td)
            spec = self._spec(specs, "task-role")

            changed = sync_spec_status(
                specs,
                "task-role",
                "in-progress",
                dry=False,
                src_col="TODO",
                dst_col="IN PROGRESS",
                card_title="DEV: Task",
            )

            self.assertTrue(changed)
            text = spec.read_text(encoding="utf-8")
            self.assertIn("| planner | TODO → IN PROGRESS", text)
            self.assertNotIn("| move | TODO → IN PROGRESS", text)

    def test_sync_spec_status_writes_developer_for_in_progress_to_testing(self):
        with tempfile.TemporaryDirectory() as td:
            specs = Path(td)
            spec = self._spec(specs, "task-role")

            changed = sync_spec_status(
                specs,
                "task-role",
                "testing",
                dry=False,
                src_col="IN PROGRESS",
                dst_col="TESTING",
                card_title="DEV: Task",
            )

            self.assertTrue(changed)
            text = spec.read_text(encoding="utf-8")
            self.assertIn("| developer | IN PROGRESS → TESTING", text)
            self.assertNotIn("| move | IN PROGRESS → TESTING", text)



# ---------------------------------------------------------------------------
# Test: lifecycle hooks
# ---------------------------------------------------------------------------

class TestWorkflowHooks(unittest.TestCase):
    """Lifecycle hooks validate transitions and produce role packets without mutation."""

    def test_before_move_allows_contract_transition(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td)
            (tasks / "specs").mkdir()
            (tasks / "specs" / "task-a.md").write_text(
                "---\nstatus: ready\nstep: null\n---\n\n"
                "## Comments\n\n2026-07-04 00:00:00 | planner | estimate ok, no blockers\n",
                encoding="utf-8",
            )
            result = hooks.before_move(tasks, "task-a", "TODO", "IN PROGRESS")
            self.assertTrue(result.ok)

    def test_before_move_allows_no_qa_review_paths(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td)
            (tasks / "specs").mkdir()
            (tasks / "specs" / "task-a.md").write_text(
                "---\nstatus: in-progress\nstep: step-1\n---\n\n## Comments\n",
                encoding="utf-8",
            )
            (tasks / "specs" / "task-b.md").write_text(
                "---\nstatus: rework\nstep: step-1\n---\n\n## Comments\n",
                encoding="utf-8",
            )
            self.assertTrue(hooks.before_move(tasks, "task-a", "IN PROGRESS", "IN REVIEW").ok)
            self.assertTrue(hooks.before_move(tasks, "task-b", "REWORK", "IN REVIEW").ok)

    def test_before_move_updates_blocked_exits(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td)
            (tasks / "specs").mkdir()
            (tasks / "specs" / "task-a.md").write_text(
                "---\nstatus: blocked\nstep: step-1\n---\n\n## Comments\n",
                encoding="utf-8",
            )
            self.assertFalse(hooks.before_move(tasks, "task-a", "BLOCKED", "BACKLOG").ok)
            self.assertTrue(hooks.before_move(tasks, "task-a", "BLOCKED", "ICEBOX").ok)
            self.assertTrue(hooks.before_move(tasks, "task-a", "BLOCKED", "REWORK").ok)

    def test_before_move_denies_todo_to_in_progress_without_planner_comment(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td)
            (tasks / "specs").mkdir()
            (tasks / "specs" / "task-a.md").write_text(
                "---\nstatus: ready\nstep: null\n---\n\n## Comments\n",
                encoding="utf-8",
            )
            result = hooks.before_move(tasks, "task-a", "TODO", "IN PROGRESS")
            self.assertFalse(result.ok)
            self.assertIn("no planner comment", result.message)

    def test_before_move_allows_todo_to_backlog_rollback_without_planner_comment(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td)
            (tasks / "specs").mkdir()
            (tasks / "specs" / "task-a.md").write_text(
                "---\nstatus: ready\nstep: null\n---\n\n## Comments\n",
                encoding="utf-8",
            )
            result = hooks.before_move(tasks, "task-a", "TODO", "BACKLOG")
            self.assertTrue(result.ok)

    def test_before_move_denies_illegal_transition(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td)
            (tasks / "specs").mkdir()
            (tasks / "specs" / "task-a.md").write_text("---\nstatus: backlog\nstep: null\n---\n", encoding="utf-8")
            result = hooks.before_move(tasks, "task-a", "BACKLOG", "DONE")
            self.assertFalse(result.ok)
            self.assertIn("Cannot move BACKLOG -> DONE", result.message)

    def test_before_move_requires_spec_for_todo_plus(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td)
            (tasks / "specs").mkdir()
            result = hooks.before_move(tasks, "missing-task", "TODO", "IN PROGRESS")
            self.assertFalse(result.ok)
            self.assertIn("missing", result.message.lower())

    def test_after_move_packet_contains_role_and_checklists(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td)
            specs = tasks / "specs"
            specs.mkdir()
            (specs / "task-a.md").write_text(
                "---\nstatus: in-progress\nstep: step-1\n---\n\n"
                "## Definition of Done (DoD)\n- [x] One\n- [ ] Two\n\n"
                "## Test Checklist\n- [ ] Test\n\n"
                "## Review Checklist\n- [ ] Review\n",
                encoding="utf-8",
            )
            packet = hooks.after_move(tasks, "task-a", "TODO", "IN PROGRESS", title="Task A", role="developer")
            self.assertIn("RESUME PACKET", packet)
            self.assertIn("Role: developer", packet)
            self.assertIn("DoD 1/2", packet)





# ---------------------------------------------------------------------------
# Test: process lint gates
# ---------------------------------------------------------------------------

class TestProcessLintGates(unittest.TestCase):
    """Process lint findings protect the autonomous workflow gates."""

    def test_backlog_orphan_remains_warn(self):
        rep = lb.Report()
        lb.cross_checks({"idea-task": "BACKLOG"}, {}, {}, rep)
        self.assertEqual(rep.errors, 0)
        self.assertEqual(rep.warns, 1)
        self.assertIn("recovery:", rep.items[0][2])

    def test_todo_orphan_becomes_error(self):
        rep = lb.Report()
        lb.cross_checks({"ready-task": "TODO"}, {}, {}, rep)
        self.assertEqual(rep.errors, 1)
        self.assertIn("recovery:", rep.items[0][2])

    def test_research_like_title_without_prefix_warns(self):
        board_text = (
            "---\n\nkanban-plugin: board\n\n---\n\n"
            "## BACKLOG\n\n"
            "## ICEBOX\n\n"
            "## TODO\n\n"
            "- [ ] [[research-task|исследовать подход из видео]]\n\t➕ 2026-06-01\n\n"
            "## IN PROGRESS\n\n"
            "## BLOCKED\n\n"
            "## TESTING\n\n"
            "## IN REVIEW\n\n"
            "## REJECTED\n\n"
            "## REWORK\n\n"
            "## DONE\n\n"
            "\n%% kanban:settings\n{}\n%%\n"
        )
        rep = lb.Report()
        lb.lint_board_file(Path("demo.md"), board_text, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertTrue(any("RESEARCH:" in msg and "recovery:" in msg for msg in messages))

    def test_done_missing_history_chain_warns(self):
        rep = lb.Report()
        specs = {"task-a": {"status": "done", "itemType": "task"}}
        body = "## Changelog\n\n2026-06-01 10:00 | move | IN REVIEW → DONE\n"
        lb.cross_checks({"task-a": "DONE"}, specs, {"task-a": body}, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertTrue(any("DONE without a full history chain" in msg and "recovery:" in msg for msg in messages))

    def test_done_history_chain_accepts_no_qa_review_path(self):
        rep = lb.Report()
        specs = {"task-a": {"status": "done", "itemType": "task"}}
        body = (
            "## Changelog\n\n"
            "2026-07-09 10:00 | analyst | BACKLOG → TODO\n"
            "2026-07-09 10:10 | planner | TODO → IN PROGRESS\n"
            "2026-07-09 10:20 | developer | IN PROGRESS → IN REVIEW\n"
            "2026-07-09 10:30 | reviewer | IN REVIEW → DONE\n"
        )
        lb.cross_checks({"task-a": "DONE"}, specs, {"task-a": body}, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertFalse(any("DONE without a full history chain" in msg for msg in messages))

    def test_related_links_must_be_bidirectional(self):
        rep = lb.Report()
        specs = {
            "task-a": {"status": "backlog", "itemType": "task"},
            "task-b": {"status": "backlog", "itemType": "task"},
        }
        bodies = {
            "task-a": "## Related\n- [[task-b|Task B]]\n\n## Changelog\n",
            "task-b": "## Changelog\n",
        }
        lb.cross_checks({"task-a": "BACKLOG", "task-b": "BACKLOG"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertTrue(any("has no reciprocal link back to" in msg for msg in messages))
        self.assertGreaterEqual(rep.errors, 1)

    def test_related_links_accept_reciprocal_pair(self):
        rep = lb.Report()
        specs = {
            "task-a": {"status": "backlog", "itemType": "task"},
            "task-b": {"status": "backlog", "itemType": "task"},
        }
        bodies = {
            "task-a": "## Related\n- [[task-b|Task B]]\n\n## Changelog\n",
            "task-b": "## Related\n- [[task-a|Task A]]\n\n## Changelog\n",
        }
        lb.cross_checks({"task-a": "BACKLOG", "task-b": "BACKLOG"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertFalse(any("## Related" in msg for msg in messages))

    def test_depends_on_requires_reverse_blocks(self):
        rep = lb.Report()
        specs = {
            "task-a": {"status": "ready", "itemType": "task", "dependsOn": "[task-b]", "blocks": "[]"},
            "task-b": {"status": "done", "itemType": "task", "dependsOn": "[]", "blocks": "[]"},
        }
        bodies = {"task-a": "## Changelog\n", "task-b": "## Changelog\n"}
        lb.cross_checks({"task-a": "TODO", "task-b": "DONE"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertTrue(any("dependsOn `task-b` is not mirrored" in msg for msg in messages))
        self.assertGreaterEqual(rep.errors, 1)

    def test_blocks_requires_reverse_depends_on(self):
        rep = lb.Report()
        specs = {
            "task-a": {"status": "in-progress", "itemType": "task", "dependsOn": "[]", "blocks": "[task-b]"},
            "task-b": {"status": "backlog", "itemType": "task", "dependsOn": "[]", "blocks": "[]"},
        }
        bodies = {"task-a": "## Changelog\n", "task-b": "## Changelog\n"}
        lb.cross_checks({"task-a": "IN PROGRESS", "task-b": "BACKLOG"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertTrue(any("blocks `task-b` is not mirrored" in msg for msg in messages))
        self.assertGreaterEqual(rep.errors, 1)

    def test_blocking_relationship_accepts_reciprocal_pair(self):
        rep = lb.Report()
        specs = {
            "task-a": {"status": "ready", "itemType": "task", "dependsOn": "[task-b]", "blocks": "[]"},
            "task-b": {"status": "done", "itemType": "task", "dependsOn": "[]", "blocks": "[task-a]"},
        }
        bodies = {"task-a": "## Changelog\n", "task-b": "## Changelog\n"}
        lb.cross_checks({"task-a": "TODO", "task-b": "DONE"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertFalse(any("is not mirrored" in msg for msg in messages))

    def test_backlog_epic_plain_tasks_warns(self):
        rep = lb.Report()
        specs = {
            "epic-a": {"status": "backlog", "itemType": "epic"},
        }
        bodies = {
            "epic-a": "## Tasks\n- [ ] Define child task later\n\n## Changelog\n",
        }
        lb.cross_checks({"epic-a": "BACKLOG"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertEqual(rep.errors, 0)
        self.assertTrue(any("plain-text item" in msg and "new-task" in msg for msg in messages))

    def test_ready_epic_plain_tasks_errors(self):
        rep = lb.Report()
        specs = {
            "epic-a": {"status": "ready", "itemType": "epic"},
        }
        bodies = {
            "epic-a": "## Tasks\n- [ ] Define child task later\n\n## Changelog\n",
        }
        lb.cross_checks({"epic-a": "TODO"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertGreaterEqual(rep.errors, 1)
        self.assertTrue(any("plain-text item" in msg and "child spec" in msg for msg in messages))

    def test_epic_tasks_accept_real_child_wikilinks(self):
        rep = lb.Report()
        specs = {
            "epic-a": {"status": "backlog", "itemType": "epic"},
            "task-a": {"status": "backlog", "itemType": "task", "parentId": "epic-a"},
        }
        bodies = {
            "epic-a": "## Tasks\n- [ ] [[task-a|Task A]]\n\n## Changelog\n",
            "task-a": "## Changelog\n",
        }
        lb.cross_checks({"epic-a": "BACKLOG", "task-a": "BACKLOG"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertFalse(any("plain-text item" in msg for msg in messages))
        self.assertFalse(any("parentId" in msg for msg in messages))

    def test_ready_epic_without_children_errors(self):
        # User directive: an epic must have decomposed child tasks;
        # an empty `## Tasks` outside intake is an ERROR (decompose it or make it a task).
        rep = lb.Report()
        specs = {"epic-a": {"status": "ready", "itemType": "epic"}}
        bodies = {"epic-a": "## Tasks\n\n## Changelog\n"}
        lb.cross_checks({"epic-a": "TODO"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertGreaterEqual(rep.errors, 1)
        self.assertTrue(any("without decomposition" in msg and "task" in msg for msg in messages))

    def test_backlog_epic_without_children_warns_not_errors(self):
        # During intake, decomposition may not be done yet — WARN, not ERROR.
        rep = lb.Report()
        specs = {"epic-a": {"status": "backlog", "itemType": "epic"}}
        bodies = {"epic-a": "## Tasks\n\n## Changelog\n"}
        lb.cross_checks({"epic-a": "BACKLOG"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertEqual(rep.errors, 0)
        self.assertTrue(any("without decomposition" in msg for msg in messages))

    def test_ready_epic_with_child_no_decomposition_error(self):
        rep = lb.Report()
        specs = {
            "epic-a": {"status": "ready", "itemType": "epic"},
            "task-a": {"status": "ready", "itemType": "task", "parentId": "epic-a"},
        }
        bodies = {
            "epic-a": "## Tasks\n- [ ] [[task-a|Task A]]\n\n## Changelog\n",
            "task-a": "## Changelog\n",
        }
        lb.cross_checks({"epic-a": "TODO", "task-a": "TODO"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertFalse(any("without decomposition" in msg for msg in messages))

    def test_task_without_tasks_section_not_flagged(self):
        # The rule applies only to itemType==epic; a task without `## Tasks` is valid.
        rep = lb.Report()
        specs = {"task-a": {"status": "done", "itemType": "task"}}
        bodies = {"task-a": "## Definition of Done (DoD)\n- [x] ok\n\n## Changelog\n"}
        lb.cross_checks({"task-a": "DONE"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertFalse(any("without decomposition" in msg for msg in messages))

    def test_scoped_lint_loads_epic_task_children(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks = root / "tasks"
            specs = tasks / "specs"
            specs.mkdir(parents=True)
            (tasks / "demo.md").write_text(
                "---\n\nkanban-plugin: board\n\n---\n\n"
                "## BACKLOG\n\n"
                "- [ ] [[epic-a|EPIC: Epic A]]\n\t➕ 2026-06-01\n\n"
                "- [ ] [[task-a|DOC: Task A]]\n\t➕ 2026-06-01\n\n"
                "## ICEBOX\n\n## TODO\n\n## IN PROGRESS\n\n## BLOCKED\n\n"
                "## TESTING\n\n## IN REVIEW\n\n## UAT\n\n## REJECTED\n\n## REWORK\n\n"
                "## DONE\n\n\n%% kanban:settings\n{}\n%%\n",
                encoding="utf-8",
            )
            (specs / "epic-a.md").write_text(
                "---\n"
                "flowId: demo/epic/epic-a\nitemType: epic\nstatus: backlog\n"
                "parentId: null\nstep: null\nowner: analyst\npriority: high\n"
                "createdAt: 2026-06-01 10:00\nupdatedAt: 2026-06-01 10:00\n"
                "reminder: null\nstartedAt: null\ntestingAt: null\nreviewAt: null\ndoneAt: null\n"
                "dependsOn: []\nblocks: []\n"
                "---\n\n"
                "# Epic A\n\n"
                "## Definition of Done (DoD)\n- [ ] Done\n\n"
                "## Tasks\n- [ ] [[task-a|Task A]]\n\n"
                "## Review Checklist\n- [ ] Reviewed\n\n"
                "## Changelog\n\n## Comments\n",
                encoding="utf-8",
            )
            (specs / "task-a.md").write_text(
                "---\n"
                "flowId: demo/task/task-a\nitemType: task\nstatus: backlog\n"
                "parentId: epic-a\nstep: null\nowner: analyst\npriority: medium\n"
                "createdAt: 2026-06-01 10:00\nupdatedAt: 2026-06-01 10:00\n"
                "reminder: null\nstartedAt: null\ntestingAt: null\nreviewAt: null\ndoneAt: null\n"
                "dependsOn: []\nblocks: []\n"
                "---\n\n"
                "# Task A\n\n"
                "## Definition of Done (DoD)\n- [ ] Done\n\n"
                "## Test Checklist\n- [ ] Test\n\n"
                "## Review Checklist\n- [ ] Reviewed\n\n"
                "## Changelog\n\n## Comments\n",
                encoding="utf-8",
            )

            import io
            from contextlib import redirect_stdout
            old_argv = sys.argv[:]
            try:
                sys.argv = ["lint_board.py", str(root), "--slug", "epic-a"]
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc_val = lb.main()
                output = buf.getvalue()
            finally:
                sys.argv = old_argv

            self.assertEqual(rc_val, 0, output)
            self.assertNotIn("Spec not found", output)
            self.assertNotIn("parentId", output)

    def test_scoped_lint_loads_dependency_closure_and_flags_prose_yaml_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks = root / "tasks"
            specs = tasks / "specs"
            specs.mkdir(parents=True)
            (tasks / "demo.md").write_text(
                "---\n\nkanban-plugin: board\n\n---\n\n"
                "## BACKLOG\n\n## ICEBOX\n\n## TODO\n\n## IN PROGRESS\n\n"
                "## BLOCKED\n\n## TESTING\n\n## IN REVIEW\n\n## UAT\n\n"
                "- [ ] [[epic-a|EPIC: Epic A]]\n\t➕ 2026-06-01\n\n"
                "## REJECTED\n\n## REWORK\n\n## DONE\n\n"
                "- [x] [[research-a|RESEARCH: Research A]]\n\t➕ 2026-06-01 ✅ 2026-06-01\n\n"
                "\n%% kanban:settings\n{}\n%%\n",
                encoding="utf-8",
            )
            (specs / "epic-a.md").write_text(
                "---\n"
                "flowId: demo/epic/epic-a\nitemType: epic\nstatus: uat\n"
                "parentId: null\nstep: null\nowner: analyst\npriority: high\n"
                "createdAt: 2026-06-01 10:00\nupdatedAt: 2026-06-01 10:00\n"
                "reminder: null\nstartedAt: 2026-06-01 10:00\ntestingAt: null\nreviewAt: null\ndoneAt: null\n"
                "dependsOn: []\nblocks: []\n"
                "---\n\n"
                "# Epic A\n\n"
                "## Definition of Done (DoD)\n- [x] Done\n\n"
                "## Dependencies\n- Depends on: [[research-a|Research A]]\n- Blocks: —\n\n"
                "## Review Checklist\n- [x] Reviewed\n\n"
                "## Changelog\n\n## Comments\n",
                encoding="utf-8",
            )
            (specs / "research-a.md").write_text(
                "---\n"
                "flowId: demo/task/research-a\nitemType: task\nstatus: done\n"
                "parentId: null\nstep: null\nowner: analyst\npriority: medium\n"
                "createdAt: 2026-06-01 09:00\nupdatedAt: 2026-06-01 09:00\n"
                "reminder: null\nstartedAt: 2026-06-01 09:00\ntestingAt: null\nreviewAt: null\ndoneAt: 2026-06-01 09:30\n"
                "dependsOn: []\nblocks: []\n"
                "---\n\n"
                "# Research A\n\n"
                "## Definition of Done (DoD)\n- [x] Done\n\n"
                "## Changelog\n\n## Comments\n",
                encoding="utf-8",
            )

            import io
            from contextlib import redirect_stdout
            old_argv = sys.argv[:]
            try:
                sys.argv = ["lint_board.py", str(root), "--slug", "epic-a"]
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc_val = lb.main()
                output = buf.getvalue()
            finally:
                sys.argv = old_argv

            self.assertEqual(rc_val, 1, output)
            self.assertIn("dependsOn", output)
            self.assertIn("research-a", output)

    def test_artifact_slug_must_not_duplicate_task_slug(self):
        with tempfile.TemporaryDirectory() as td:
            tasks = Path(td) / "tasks"
            (tasks / "artifacts").mkdir(parents=True)
            (tasks / "artifacts" / "task-a.md").write_text(
                "---\nitemType: artifact\nlinkedTask: task-a\nstatus: actual\n---\n",
                encoding="utf-8",
            )
            rep = lb.Report()
            lb.cross_checks(
                {"task-a": "BACKLOG"},
                {"task-a": {"status": "backlog", "itemType": "task"}},
                {"task-a": "## Changelog\n"},
                rep,
                tasks_dir=tasks,
            )
            messages = [msg for _sev, _scope, msg in rep.items]
            self.assertTrue(any("duplicates `tasks/specs/task-a.md`" in msg for msg in messages))
            self.assertGreaterEqual(rep.errors, 1)

    def test_review_gate_accepts_canonical_dod_heading(self):
        rep = lb.Report()
        body = (
            "## Definition of Done (DoD)\n"
            "- [x] Done item\n\n"
            "## Review Checklist\n"
            "- [x] Reviewed\n\n"
            "## Test Checklist\n"
            "- [x] Tested\n"
        )
        lb.check_checklist_gap(body, "Definition of Done", "specs/task-a.md", rep)
        self.assertEqual(rep.errors, 0)

    def test_direct_review_path_does_not_require_test_checklist(self):
        rep = lb.Report()
        text = (
            "---\n"
            "flowId: demo/task/task-a\nitemType: task\nstatus: review\n"
            "parentId: null\nstep: null\nowner: user\npriority: medium\n"
            "createdAt: 2026-07-09 10:00\nupdatedAt: 2026-07-09 10:00\n"
            "reminder: null\nstartedAt: 2026-07-09 10:00\ntestingAt: null\nreviewAt: 2026-07-09 11:00\ndoneAt: null\n"
            "dependsOn: []\nblocks: []\n"
            "---\n\n"
            "# Task A\n\n"
            "## Definition of Done (DoD)\n- [x] Done\n\n"
            "## Test Checklist\n- [ ] QA intentionally skipped\n\n"
            "## Review Checklist\n- [x] Reviewed\n\n"
            "## Changelog\n2026-07-09 11:00 | developer | IN PROGRESS → IN REVIEW\n\n"
            "## Comments\n"
        )
        lb.lint_spec_file(Path("task-a.md"), text, rep)
        self.assertEqual(rep.errors, 0)

# ---------------------------------------------------------------------------
# Test: resume command
# ---------------------------------------------------------------------------

class TestResumeCommand(unittest.TestCase):
    """resume.py finds the active task and prints a read-only packet."""

    def _workspace(self, td):
        root = Path(td)
        tasks = root / "tasks"
        specs = tasks / "specs"
        specs.mkdir(parents=True)
        (tasks / "demo.md").write_text(
            "---\n\nkanban-plugin: board\n\n---\n\n"
            "## BACKLOG\n\n"
            "## ICEBOX\n\n"
            "## TODO\n\n"
            "## IN PROGRESS\n\n"
            "- [ ] [[task-a|DEV: Task A]]\n\t➕ 2026-06-01 🛫 2026-06-01\n\n"
            "## BLOCKED\n\n"
            "## TESTING\n\n"
            "## IN REVIEW\n\n"
            "## REJECTED\n\n"
            "## REWORK\n\n"
            "## DONE\n\n"
            "\n%% kanban:settings\n{}\n%%\n",
            encoding="utf-8",
        )
        (specs / "task-a.md").write_text(
            "---\nstatus: in-progress\nstep: step-2\n---\n\n"
            "## Definition of Done (DoD)\n- [x] One\n- [ ] Two\n\n"
            "## Output / Артефакты\n- [[artifact-a|Artifact A]]\n- path/to/file.md\n\n"
            "## Test Checklist\n- [ ] Resume для IN PROGRESS показывает developer/research role.\n\n"
            "## Review Checklist\n- [ ] Все пункты DoD выполнены\n\n"
            "## Comments\n\n"
            "2026-06-27 10:00 | user | !!!ВНИМАНИЕ!!! preserve this context\n",
            encoding="utf-8",
        )
        return root, tasks

    def test_find_single_active_task(self):
        with tempfile.TemporaryDirectory() as td:
            _, tasks = self._workspace(td)
            task = resume.find_single_active_task(tasks)
            self.assertEqual(task.slug, "task-a")
            self.assertEqual(task.column, "IN PROGRESS")

    def test_packet_contains_required_resume_fields(self):
        with tempfile.TemporaryDirectory() as td:
            _, tasks = self._workspace(td)
            task = resume.find_single_active_task(tasks)
            packet = resume.build_packet(tasks, task)
            self.assertIn("Column/status: IN PROGRESS/in-progress", packet)
            self.assertIn("Role: developer", packet)
            self.assertIn("Step: step-2", packet)
            self.assertIn("!!!ВНИМАНИЕ!!! preserve this context", packet)
            self.assertIn("DoD 1/2", packet)
            self.assertIn("[[artifact-a|Artifact A]]", packet)
            self.assertIn("Next allowed action:", packet)
            self.assertIn("kanban.py move \".\" task-a TESTING", packet)

    def test_main_does_not_mutate_files(self):
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            board = tasks / "demo.md"
            spec = tasks / "specs" / "task-a.md"
            before_board = board.read_text(encoding="utf-8")
            before_spec = spec.read_text(encoding="utf-8")
            old_argv = sys.argv[:]
            try:
                sys.argv = ["resume.py", str(root), "task-a"]
                self.assertEqual(resume.main(), 0)
            finally:
                sys.argv = old_argv
            self.assertEqual(board.read_text(encoding="utf-8"), before_board)
            self.assertEqual(spec.read_text(encoding="utf-8"), before_spec)

    def test_uat_column_is_active(self):
        """UAT tasks are included in ACTIVE_COLUMNS so resume finds them."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks = root / "tasks"
            (tasks / "specs").mkdir(parents=True)
            (tasks / "demo.md").write_text(
                "---\n\nkanban-plugin: board\n\n---\n\n"
                "## BACKLOG\n\n## ICEBOX\n\n## TODO\n\n## IN PROGRESS\n\n"
                "## BLOCKED\n\n## TESTING\n\n## IN REVIEW\n\n"
                "## UAT\n\n"
                "- [ ] [[uat-task|REFACTOR: UAT task]]\n\t➕ 2026-06-28\n\n"
                "## REJECTED\n\n## REWORK\n\n## DONE\n\n"
                "\n%% kanban:settings\n{}\n%%\n",
                encoding="utf-8",
            )
            (tasks / "specs" / "uat-task.md").write_text(
                "---\nstatus: uat\nstep: step-1\n---\n\n"
                "## Definition of Done (DoD)\n- [x] Done\n\n"
                "## Comments\n",
                encoding="utf-8",
            )
            task = resume.find_single_active_task(tasks)
            self.assertEqual(task.slug, "uat-task")
            self.assertEqual(task.column, "UAT")

    def test_idle_fallback_returns_next_task(self):
        """resume main() exits 0 and prints next task when queue is idle."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            tasks = root / "tasks"
            (tasks / "specs").mkdir(parents=True)
            (tasks / "demo.md").write_text(
                "---\n\nkanban-plugin: board\n\n---\n\n"
                "## BACKLOG\n\n"
                "- [ ] [[idle-task|DEV: Idle Task]]\n\t➕ 2026-06-28\n\n"
                "## ICEBOX\n\n## TODO\n\n## IN PROGRESS\n\n"
                "## BLOCKED\n\n## TESTING\n\n## IN REVIEW\n\n"
                "## UAT\n\n## REJECTED\n\n## REWORK\n\n## DONE\n\n"
                "\n%% kanban:settings\n{}\n%%\n",
                encoding="utf-8",
            )
            old_argv = sys.argv[:]
            try:
                sys.argv = ["resume.py", str(root)]
                import io
                from contextlib import redirect_stdout
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = resume.main()
                output = buf.getvalue()
            finally:
                sys.argv = old_argv
            self.assertEqual(rc, 0)
            self.assertIn("idle-task", output)

    def test_full_checklist_matches_role_prompt(self):
        """resume --full-checklist output is byte-identical to the legacy
        role_prompt.py CLI for the same column/title (unify-context-recovery-commands)."""
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            import io
            from contextlib import redirect_stdout

            old_argv = sys.argv[:]
            buf_resume = io.StringIO()
            try:
                sys.argv = ["resume.py", str(root), "task-a", "--full-checklist"]
                with redirect_stdout(buf_resume):
                    rc_resume = resume.main()
            finally:
                sys.argv = old_argv
            self.assertEqual(rc_resume, 0)

            old_argv = sys.argv[:]
            buf_role = io.StringIO()
            try:
                sys.argv = ["role_prompt.py", str(root), "IN PROGRESS", "--title", "DEV: Task A"]
                with redirect_stdout(buf_role):
                    rc_role = role_prompt.main()
            finally:
                sys.argv = old_argv
            self.assertEqual(rc_role, 0)

            self.assertEqual(buf_resume.getvalue(), buf_role.getvalue())
            self.assertIn("=== РОЛЬ:", buf_resume.getvalue())
            self.assertIn("=== КОНЕЦ ЧЕКЛИСТА ===", buf_resume.getvalue())

    def test_brief_matches_spec_brief(self):
        """resume --brief output is byte-identical to the legacy spec_brief.py
        CLI for the same slug (unify-context-recovery-commands)."""
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            import io
            from contextlib import redirect_stdout

            old_argv = sys.argv[:]
            buf_resume = io.StringIO()
            try:
                sys.argv = ["resume.py", str(root), "task-a", "--brief"]
                with redirect_stdout(buf_resume):
                    rc_resume = resume.main()
            finally:
                sys.argv = old_argv
            self.assertEqual(rc_resume, 0)

            old_argv = sys.argv[:]
            buf_brief = io.StringIO()
            try:
                sys.argv = ["spec_brief.py", str(root), "task-a"]
                with redirect_stdout(buf_brief):
                    rc_brief = spec_brief.main()
            finally:
                sys.argv = old_argv
            self.assertEqual(rc_brief, 0)

            self.assertEqual(buf_resume.getvalue(), buf_brief.getvalue())
            self.assertIn("=== SPEC BRIEF: task-a ===", buf_resume.getvalue())

    def test_flags_do_not_mutate_files(self):
        """--full-checklist and --brief are read-only, same guarantee as default resume."""
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            board = tasks / "demo.md"
            spec = tasks / "specs" / "task-a.md"
            before_board = board.read_text(encoding="utf-8")
            before_spec = spec.read_text(encoding="utf-8")
            for flag in ("--full-checklist", "--brief"):
                old_argv = sys.argv[:]
                try:
                    sys.argv = ["resume.py", str(root), "task-a", flag]
                    self.assertEqual(resume.main(), 0)
                finally:
                    sys.argv = old_argv
            self.assertEqual(board.read_text(encoding="utf-8"), before_board)
            self.assertEqual(spec.read_text(encoding="utf-8"), before_spec)


# ---------------------------------------------------------------------------
# Test: remove_card
# ---------------------------------------------------------------------------

_MINIMAL_BOARD = (
    "---\n\nkanban-plugin: board\n\n---\n\n"
    "## BACKLOG\n\n"
    "- [ ] [[task-alpha|Task Alpha]]\n\t➕ 2026-06-01\n\n"
    "## ICEBOX\n\n## TODO\n\n## IN PROGRESS\n\n## BLOCKED\n\n"
    "## TESTING\n\n## IN REVIEW\n\n## UAT\n\n## REJECTED\n\n## REWORK\n\n"
    "## DONE\n\n\n"
    "%% kanban:settings\n{}\n%%\n"
)


class TestRemoveCard(unittest.TestCase):
    """remove_card removes a card block from the board."""

    def _workspace(self, td):
        root = Path(td)
        tasks = root / "tasks"
        (tasks / "specs").mkdir(parents=True)
        board = tasks / "demo.md"
        board.write_text(_MINIMAL_BOARD, encoding="utf-8")
        return root, tasks, board

    def test_removes_existing_card(self):
        import remove_card as rc
        with tempfile.TemporaryDirectory() as td:
            root, tasks, board = self._workspace(td)
            ret, msg = rc.remove_card_from_board(tasks, "task-alpha", board_hint="demo.md")
            self.assertEqual(ret, 0)
            self.assertNotIn("task-alpha", board.read_text(encoding="utf-8"))

    def test_warns_when_spec_exists(self):
        import remove_card as rc
        with tempfile.TemporaryDirectory() as td:
            root, tasks, board = self._workspace(td)
            (tasks / "specs" / "task-alpha.md").write_text(
                "---\nstatus: backlog\n---\n", encoding="utf-8")
            ret, msg = rc.remove_card_from_board(tasks, "task-alpha", board_hint="demo.md")
            self.assertEqual(ret, 0)
            self.assertIn("WARNING", msg)

    def test_error_when_not_found(self):
        import remove_card as rc
        with tempfile.TemporaryDirectory() as td:
            root, tasks, board = self._workspace(td)
            ret, msg = rc.remove_card_from_board(tasks, "no-such-card", board_hint="demo.md")
            self.assertEqual(ret, 1)

    def test_dry_run_does_not_mutate(self):
        import remove_card as rc
        with tempfile.TemporaryDirectory() as td:
            root, tasks, board = self._workspace(td)
            before = board.read_text(encoding="utf-8")
            rc.remove_card_from_board(tasks, "task-alpha", board_hint="demo.md", dry_run=True)
            self.assertEqual(board.read_text(encoding="utf-8"), before)


# ---------------------------------------------------------------------------
# Test: check_item (checkbox toggle)
# ---------------------------------------------------------------------------

def _write_check_spec(specs_dir, slug, body):
    p = specs_dir / f"{slug}.md"
    p.write_text(
        f"---\nflowId: demo/task/{slug}\nitemType: task\nstatus: in-progress\n"
        f"parentId: null\nstep: null\nowner: analyst\npriority: medium\n"
        f"createdAt: 2026-06-01 10:00\nupdatedAt: 2026-06-01 10:00\n"
        f"reminder: null\nstartedAt: null\ntestingAt: null\nreviewAt: null\ndoneAt: null\n"
        f"dependsOn: []\nblocks: []\n---\n\n# Test Task\n\n{body}",
        encoding="utf-8",
    )


class TestCheckItem(unittest.TestCase):
    """check_item toggles checkboxes; supports EN + RU aliases."""

    _SPEC_BODY = (
        "## Definition of Done (DoD)\n"
        "- [ ] first\n"
        "- [ ] second\n\n"
        "## Subtasks\n"
        "- [ ] sub-one\n\n"
        "## Comments\n"
    )

    def test_check_dod_item(self):
        import check_item as ci
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            specs = root / "tasks" / "specs"
            specs.mkdir(parents=True)
            _write_check_spec(specs, "ci-task", self._SPEC_BODY)
            transform = ci.make_check_transform(
                "ci-task", "Definition of Done (DoD)", [1], False)
            rc_val, _msg = ku.mutate_spec(root / "tasks", "ci-task", transform)
            self.assertEqual(rc_val, 0)
            body = (specs / "ci-task.md").read_text(encoding="utf-8")
            self.assertIn("- [x] first", body)
            self.assertIn("- [ ] second", body)

    def test_check_subtasks_en_header(self):
        import check_item as ci
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            specs = root / "tasks" / "specs"
            specs.mkdir(parents=True)
            _write_check_spec(specs, "ci-task", self._SPEC_BODY)
            transform = ci.make_check_transform("ci-task", "Subtasks", [1], False)
            rc_val, _msg = ku.mutate_spec(root / "tasks", "ci-task", transform)
            self.assertEqual(rc_val, 0)
            self.assertIn("- [x] sub-one",
                          (specs / "ci-task.md").read_text(encoding="utf-8"))

    def test_check_subtasks_ru_alias(self):
        import check_item as ci
        ru_spec = "Подзадачи"  # Подзадачи
        ru_body = f"## {ru_spec}\n- [ ] sub-ru\n\n## Comments\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            specs = root / "tasks" / "specs"
            specs.mkdir(parents=True)
            _write_check_spec(specs, "ci-task", ru_body)
            transform = ci.make_check_transform("ci-task", "Subtasks", [1], False)
            rc_val, _msg = ku.mutate_spec(root / "tasks", "ci-task", transform)
            self.assertEqual(rc_val, 0)
            self.assertIn("- [x] sub-ru",
                          (specs / "ci-task.md").read_text(encoding="utf-8"))

    def test_uncheck_item(self):
        import check_item as ci
        checked = "## Definition of Done (DoD)\n- [x] already-done\n\n## Comments\n"
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            specs = root / "tasks" / "specs"
            specs.mkdir(parents=True)
            _write_check_spec(specs, "ci-task", checked)
            transform = ci.make_check_transform(
                "ci-task", "Definition of Done (DoD)", [1], False, uncheck=True)
            rc_val, _msg = ku.mutate_spec(root / "tasks", "ci-task", transform)
            self.assertEqual(rc_val, 0)
            self.assertIn("- [ ] already-done",
                          (specs / "ci-task.md").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Test: check.py without --slug emits an actionable hint, not raw argparse
# ---------------------------------------------------------------------------

class TestCheckMissingSlug(unittest.TestCase):
    """`kanban.py check "."` without --slug should point to lint / --slug via an
    actionable message (exit 2) and never leak the internal module name in the
    argparse prog (dogfooding 2026-07-09 live incident)."""

    @staticmethod
    def _run(*argv):
        import io
        import contextlib
        import check
        err = io.StringIO()
        old_argv = sys.argv[:]
        try:
            sys.argv = ["check.py", *argv]
            with contextlib.redirect_stderr(err):
                rc_val = check.main()
            return rc_val, err.getvalue()
        finally:
            sys.argv = old_argv

    def test_missing_slug_returns_2_with_actionable_hint(self):
        rc_val, stderr = self._run(".")
        self.assertEqual(rc_val, 2)
        self.assertIn("lint", stderr)
        self.assertIn("--slug", stderr)

    def test_argparse_errors_use_facade_prog_not_module_name(self):
        import io
        import contextlib
        err = io.StringIO()
        old_argv = sys.argv[:]
        try:
            import check
            sys.argv = ["check.py", "--bogus-flag"]
            with contextlib.redirect_stderr(err):
                with self.assertRaises(SystemExit):
                    check.main()
        finally:
            sys.argv = old_argv
        self.assertIn("kanban.py check", err.getvalue())
        self.assertNotIn("check.py:", err.getvalue())


# ---------------------------------------------------------------------------
# Test: documentation source-of-truth guards
# ---------------------------------------------------------------------------

class TestDocumentationContracts(unittest.TestCase):
    """Documentation should point to canonical references instead of duplicating them."""

    def test_skill_section_10_delegates_script_tiers_to_readme(self):
        skill_root = _SCRIPTS.parent
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        marker = "## 10. Automated Checks"
        next_marker = "## 11. Session Commands"
        self.assertIn(marker, skill_text)
        self.assertIn(next_marker, skill_text)
        section = skill_text.split(marker, 1)[1].split(next_marker, 1)[0]

        self.assertIn("scripts/README.md", section)
        self.assertNotIn("| Script |", section)
        self.assertNotIn("| Purpose |", section)

class TestLoopMetricsScope(unittest.TestCase):
    """metrics board and project scope filtering is deterministic."""

    @staticmethod
    def _workspace(td):
        root = Path(td)
        tasks = root / "tasks"
        specs = tasks / "specs"
        specs.mkdir(parents=True)
        (tasks / "demo.md").write_text(_MINIMAL_BOARD, encoding="utf-8")
        (tasks / "other.md").write_text(
            _MINIMAL_BOARD.replace("task-alpha", "other-task").replace("Task Alpha", "Other Task"),
            encoding="utf-8",
        )
        (specs / "task-alpha.md").write_text(
            "---\n"
            "flowId: demo/task/task-alpha\nitemType: task\nstatus: backlog\n"
            "parentId: null\nstep: null\nowner: user\npriority: medium\n"
            "createdAt: 2026-06-01 10:00\nupdatedAt: 2026-06-01 10:00\n"
            "reminder: null\nstartedAt: null\ntestingAt: null\nreviewAt: null\ndoneAt: null\n"
            "dependsOn: []\nblocks: []\n"
            "---\n\n"
            "# Task Alpha\n\n"
            "## Definition of Done (DoD)\n- [ ] Done\n\n"
            "## Test Checklist\n- [ ] Pending check\n\n"
            "## Changelog\n\n## Comments\n",
            encoding="utf-8",
        )
        (specs / "other-task.md").write_text(
            "---\n"
            "flowId: other/task/other-task\nitemType: task\nstatus: review\n"
            "parentId: null\nstep: null\nowner: user\npriority: medium\n"
            "createdAt: 2026-06-01 10:00\nupdatedAt: 2026-06-01 10:00\n"
            "reminder: null\nstartedAt: null\ntestingAt: null\nreviewAt: null\ndoneAt: null\n"
            "dependsOn: []\nblocks: []\n"
            "---\n\n"
            "# Other Task\n\n"
            "## Definition of Done (DoD)\n- [x] Done\n\n"
            "## Test Checklist\n- [x] Tested\n\n"
            "## Review Checklist\n- [x] Reviewed\n\n"
            "## Changelog\n\n## Comments\n",
            encoding="utf-8",
        )
        return root, tasks

    def test_metrics_board_scope(self):
        with tempfile.TemporaryDirectory() as td:
            root, _tasks = self._workspace(td)
            output = loop_metrics.render(root, board="demo.md")

        self.assertIn("Scope: board demo.md", output)
        self.assertIn("| specs | 1 |", output)

    def test_metrics_project_scope_matches_board_stem(self):
        with tempfile.TemporaryDirectory() as td:
            root, _tasks = self._workspace(td)
            output = loop_metrics.render(root, project="demo")

        self.assertIn("Scope: project demo", output)
        self.assertIn("| specs | 1 |", output)
        self.assertNotIn("other-task", output)


# ---------------------------------------------------------------------------
# Test: set_card_tags --title (canonical card retitle)
# ---------------------------------------------------------------------------

class TestSetCardTitle(unittest.TestCase):
    """`tags --title` retitles a card's board alias + spec H1 in place."""

    @staticmethod
    def _workspace(td):
        root = Path(td)
        tasks = root / "tasks"
        specs = tasks / "specs"
        specs.mkdir(parents=True)
        board_text = (
            "---\n\nkanban-plugin: board\n\n---\n\n"
            "## BACKLOG\n\n"
            "- [ ] [[task-alpha|Task Alpha]]\n\t➕ 2026-06-01\n\n"
            "- [ ] [[task-other|Other Card]]\n\t➕ 2026-06-01 🟨\n\n"
            "## ICEBOX\n\n## TODO\n\n## IN PROGRESS\n\n## BLOCKED\n\n"
            "## TESTING\n\n## IN REVIEW\n\n## UAT\n\n## REJECTED\n\n## REWORK\n\n"
            "## DONE\n\n\n"
            "%% kanban:settings\n{}\n%%\n"
        )
        (tasks / "demo.md").write_text(board_text, encoding="utf-8")
        (specs / "task-alpha.md").write_text(
            "---\n"
            "flowId: demo/task/task-alpha\nitemType: task\nstatus: backlog\n"
            "parentId: null\nstep: null\nowner: analyst\npriority: medium\n"
            "createdAt: 2026-06-01 10:00\nupdatedAt: 2026-06-01 10:00\n"
            "reminder: null\nstartedAt: null\ntestingAt: null\nreviewAt: null\ndoneAt: null\n"
            "dependsOn: []\nblocks: []\n"
            "---\n\n"
            "# 📋 Task Alpha\n\n"
            "## Definition of Done (DoD)\n- [ ] Done\n\n"
            "## Changelog\n\n2026-06-01 10:00:00 | analyst | Task created\n\n"
            "## Comments\n",
            encoding="utf-8",
        )
        return root, tasks

    @staticmethod
    def _run(root, *extra_args):
        import set_card_tags as sct
        old_argv = sys.argv[:]
        try:
            sys.argv = ["set_card_tags.py", str(root), *extra_args, "--board", "demo.md"]
            return sct.main()
        finally:
            sys.argv = old_argv

    def test_title_changes_alias_keeps_column_position_and_tags(self):
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            rc_val = self._run(root, "task-alpha", "--title", "FIX: Renamed Task")
            self.assertEqual(rc_val, 0)
            board = (tasks / "demo.md").read_text(encoding="utf-8")
            self.assertIn("[[task-alpha|FIX: Renamed Task]]", board)
            # tag line untouched
            self.assertIn("➕ 2026-06-01", board)
            # column/position preserved: still under BACKLOG, before task-other
            backlog_section = board.split("## BACKLOG", 1)[1].split("## ICEBOX", 1)[0]
            self.assertLess(backlog_section.index("task-alpha"), backlog_section.index("task-other"))
            # sibling card untouched
            self.assertIn("[[task-other|Other Card]]", board)

    def test_title_syncs_spec_h1_updated_at_and_changelog(self):
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            rc_val = self._run(root, "task-alpha", "--title", "FIX: Renamed Task")
            self.assertEqual(rc_val, 0)
            spec = (tasks / "specs" / "task-alpha.md").read_text(encoding="utf-8")
            self.assertIn("# 📋 FIX: Renamed Task", spec)
            self.assertNotIn("updatedAt: 2026-06-01 10:00\n", spec)
            self.assertIn("retitle:", spec)
            self.assertIn("Task Alpha", spec)  # old title recorded in changelog entry
            self.assertIn("FIX: Renamed Task", spec)

    def test_title_rejects_pipe_and_closing_brackets(self):
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            before = (tasks / "demo.md").read_text(encoding="utf-8")
            rc_pipe = self._run(root, "task-alpha", "--title", "bad|title")
            rc_brackets = self._run(root, "task-alpha", "--title", "bad]]title")
            self.assertEqual(rc_pipe, 1)
            self.assertEqual(rc_brackets, 1)
            self.assertEqual((tasks / "demo.md").read_text(encoding="utf-8"), before)

    def test_dry_run_does_not_mutate_board_or_spec(self):
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            before_board = (tasks / "demo.md").read_text(encoding="utf-8")
            before_spec = (tasks / "specs" / "task-alpha.md").read_text(encoding="utf-8")
            rc_val = self._run(root, "task-alpha", "--title", "FIX: Renamed Task", "--dry-run")
            self.assertEqual(rc_val, 0)
            self.assertEqual((tasks / "demo.md").read_text(encoding="utf-8"), before_board)
            self.assertEqual((tasks / "specs" / "task-alpha.md").read_text(encoding="utf-8"), before_spec)


# ---------------------------------------------------------------------------
# Test: set_card_tags --reminder + --start icebox guard
# ---------------------------------------------------------------------------

class TestSetCardReminderAndIceboxGuard(unittest.TestCase):
    """`tags --reminder` mutates spec YAML `reminder` only (never startedAt / board
    tag line); `tags --start <date>` is rejected for icebox-status cards."""

    @staticmethod
    def _workspace(td):
        root = Path(td)
        tasks = root / "tasks"
        specs = tasks / "specs"
        specs.mkdir(parents=True)
        board_text = (
            "---\n\nkanban-plugin: board\n\n---\n\n"
            "## BACKLOG\n\n"
            "- [ ] [[task-alpha|Task Alpha]]\n\t➕ 2026-06-01\n\n"
            "## ICEBOX\n\n"
            "- [ ] [[task-frozen|Frozen Card]]\n\t➕ 2026-06-01\n\n"
            "## TODO\n\n## IN PROGRESS\n\n## BLOCKED\n\n"
            "## TESTING\n\n## IN REVIEW\n\n## UAT\n\n## REJECTED\n\n## REWORK\n\n"
            "## DONE\n\n\n"
            "%% kanban:settings\n{}\n%%\n"
        )
        (tasks / "demo.md").write_text(board_text, encoding="utf-8")

        def _spec(slug, status, title):
            (specs / f"{slug}.md").write_text(
                "---\n"
                f"flowId: demo/task/{slug}\nitemType: task\nstatus: {status}\n"
                "parentId: null\nstep: null\nowner: analyst\npriority: medium\n"
                "createdAt: 2026-06-01 10:00\nupdatedAt: 2026-06-01 10:00\n"
                "reminder: null\nstartedAt: null\ntestingAt: null\nreviewAt: null\ndoneAt: null\n"
                "dependsOn: []\nblocks: []\n"
                "---\n\n"
                f"# {title}\n\n"
                "## Definition of Done (DoD)\n- [ ] Done\n\n"
                "## Changelog\n\n## Comments\n",
                encoding="utf-8",
            )

        _spec("task-alpha", "backlog", "Task Alpha")
        _spec("task-frozen", "icebox", "Frozen Card")
        return root, tasks

    @staticmethod
    def _run(root, *extra_args):
        import set_card_tags as sct
        old_argv = sys.argv[:]
        try:
            sys.argv = ["set_card_tags.py", str(root), *extra_args, "--board", "demo.md"]
            return sct.main()
        finally:
            sys.argv = old_argv

    def test_reminder_sets_and_clears_without_touching_started_at(self):
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            board_before = (tasks / "demo.md").read_text(encoding="utf-8")
            spec_path = tasks / "specs" / "task-alpha.md"

            self.assertEqual(self._run(root, "task-alpha", "--reminder", "2026-08-01"), 0)
            spec = spec_path.read_text(encoding="utf-8")
            self.assertIn("reminder: 2026-08-01", spec)
            self.assertIn("startedAt: null", spec)  # startedAt untouched
            # board tag line unchanged (reminder is not a board emoji tag)
            self.assertEqual((tasks / "demo.md").read_text(encoding="utf-8"), board_before)

            self.assertEqual(self._run(root, "task-alpha", "--reminder", "none"), 0)
            spec = spec_path.read_text(encoding="utf-8")
            self.assertIn("reminder: null", spec)
            self.assertIn("startedAt: null", spec)

    def test_start_with_date_on_icebox_card_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            spec_path = tasks / "specs" / "task-frozen.md"
            board_before = (tasks / "demo.md").read_text(encoding="utf-8")

            self.assertEqual(self._run(root, "task-frozen", "--start", "2026-08-01"), 1)
            spec = spec_path.read_text(encoding="utf-8")
            self.assertIn("startedAt: null", spec)  # startedAt stays null
            # board untouched — guard fires before board mutation
            self.assertEqual((tasks / "demo.md").read_text(encoding="utf-8"), board_before)

    def test_start_none_on_icebox_card_is_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            # `--start none` clears an erroneous 🛫 — allowed for icebox
            self.assertEqual(self._run(root, "task-frozen", "--start", "none"), 0)
            spec = (tasks / "specs" / "task-frozen.md").read_text(encoding="utf-8")
            self.assertIn("startedAt: null", spec)


# ---------------------------------------------------------------------------
# Test: sync_properties priority `none` -> `null` normalization
# ---------------------------------------------------------------------------

class TestPriorityNoneNormalization(unittest.TestCase):
    """Dashboard-created cards write `priority: none`; this must normalize to the
    `null` sentinel (no priority set) instead of tripping lint as an invalid enum
    value — consistent with `tags --priority none`, which clears the board tag."""

    def test_normalize_fields_converts_none_to_null_sentinel(self):
        import sync_properties as sp
        fm = {
            "flowId": "demo/task/task-x", "itemType": "task", "status": "backlog",
            "parentId": "null", "step": "null", "owner": "analyst", "priority": "none",
            "createdAt": "2026-06-01 10:00", "updatedAt": "2026-06-01 10:00",
        }
        out, changes = sp.normalize_fields(fm, "task-x", "demo", None, False, None)
        self.assertEqual(out["priority"], "null")
        self.assertTrue(any("priority" in c and "null" in c for c in changes))

    def test_board_priority_emoji_still_wins_over_none(self):
        import sync_properties as sp
        fm = {
            "flowId": "demo/task/task-x", "itemType": "task", "status": "backlog",
            "parentId": "null", "step": "null", "owner": "analyst", "priority": "none",
            "createdAt": "2026-06-01 10:00", "updatedAt": "2026-06-01 10:00",
        }
        out, _changes = sp.normalize_fields(fm, "task-x", "demo", None, False, "high")
        self.assertEqual(out["priority"], "high")

    def test_lint_accepts_null_priority_without_error(self):
        rep = lb.Report()
        text = (
            "---\n"
            "flowId: demo/task/task-x\nitemType: task\nstatus: backlog\n"
            "parentId: null\nstep: null\nowner: analyst\npriority: null\n"
            "createdAt: 2026-06-01 10:00\nupdatedAt: 2026-06-01 10:00\n"
            "reminder: null\nstartedAt: null\ntestingAt: null\nreviewAt: null\ndoneAt: null\n"
            "dependsOn: []\nblocks: []\n"
            "---\n\n# 📋 Task X\n\n## Changelog\n\n## Comments\n"
        )
        lb.lint_spec_file(Path("task-x.md"), text, rep)
        self.assertEqual(rep.errors, 0)

    def test_lint_still_rejects_other_invalid_priority(self):
        rep = lb.Report()
        text = (
            "---\n"
            "flowId: demo/task/task-x\nitemType: task\nstatus: backlog\n"
            "parentId: null\nstep: null\nowner: analyst\npriority: urgent\n"
            "createdAt: 2026-06-01 10:00\nupdatedAt: 2026-06-01 10:00\n"
            "reminder: null\nstartedAt: null\ntestingAt: null\nreviewAt: null\ndoneAt: null\n"
            "dependsOn: []\nblocks: []\n"
            "---\n\n# 📋 Task X\n\n## Changelog\n\n## Comments\n"
        )
        lb.lint_spec_file(Path("task-x.md"), text, rep)
        self.assertGreaterEqual(rep.errors, 1)


class TestLostDoneSafeguard(unittest.TestCase):
    """doneAt is the fact of reaching (terminal) DONE and is never cleared on exit;
    a doneAt-set card outside DONE signals a false/racing move that dropped a
    completed card, which status↔column sync would otherwise reconcile silently."""

    def test_lint_warns_doneat_outside_done_column(self):
        rep = lb.Report()
        specs = {"task-a": {"status": "rejected", "itemType": "task",
                            "doneAt": "2026-07-14 20:45:41"}}
        bodies = {"task-a": "## Changelog\n\n2026-07-15 14:43 | move | DONE → REJECTED\n"}
        lb.cross_checks({"task-a": "REJECTED"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertTrue(any("a lost DONE is possible" in msg for msg in messages))
        self.assertEqual(rep.errors, 0)  # WARN, non-blocking

    def test_lint_clean_for_doneat_in_done_column(self):
        rep = lb.Report()
        specs = {"task-a": {"status": "done", "itemType": "task",
                            "doneAt": "2026-07-14 20:45:41"}}
        bodies = {"task-a": "## Changelog\n\n2026-07-14 20:45 | reviewer | IN REVIEW → DONE\n"}
        lb.cross_checks({"task-a": "DONE"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertFalse(any("lost DONE" in msg for msg in messages))

    def test_lint_ignores_null_doneat_outside_done(self):
        rep = lb.Report()
        specs = {"task-a": {"status": "rework", "itemType": "task", "doneAt": "null"}}
        bodies = {"task-a": "## Changelog\n"}
        lb.cross_checks({"task-a": "REWORK"}, specs, bodies, rep)
        messages = [msg for _sev, _scope, msg in rep.items]
        self.assertFalse(any("lost DONE" in msg for msg in messages))

    def test_sync_warns_on_backward_downgrade_from_done(self):
        import sync_properties as sp
        fm = {
            "flowId": "demo/task/task-a", "itemType": "task", "status": "done",
            "parentId": "null", "step": "null", "owner": "developer", "priority": "high",
            "createdAt": "2026-07-14 20:41", "updatedAt": "2026-07-14 20:45",
            "doneAt": "2026-07-14 20:45:41",
        }
        out, changes = sp.normalize_fields(fm, "task-a", "demo", "rejected", True, None)
        self.assertEqual(out["status"], "rejected")  # column stays source of truth
        self.assertTrue(any("LOST DONE" in c for c in changes))

    def test_sync_no_downgrade_warning_without_doneat(self):
        import sync_properties as sp
        fm = {
            "flowId": "demo/task/task-a", "itemType": "task", "status": "done",
            "parentId": "null", "step": "null", "owner": "developer", "priority": "high",
            "createdAt": "2026-07-14 20:41", "updatedAt": "2026-07-14 20:45",
            "doneAt": "null",
        }
        out, changes = sp.normalize_fields(fm, "task-a", "demo", "rejected", True, None)
        self.assertEqual(out["status"], "rejected")
        self.assertFalse(any("LOST DONE" in c for c in changes))


class TestTransitionTimestampBackfill(unittest.TestCase):
    """An interrupted move can leave a transition timestamp null while the card sits in
    its column; sync backfills it. board_status passed to normalize_fields is a STATUS
    value (parse_board maps column→status), so the lookup must be status-keyed.
    Regression: reviewAt never backfilled when keyed by column ("review" ≠ "IN REVIEW");
    testingAt/doneAt only worked by lexical coincidence (LOG-001, dogfooding 2026-07-22)."""

    def _fm(self, status, **overrides):
        fm = {
            "flowId": "demo/task/task-a", "itemType": "task", "status": status,
            "parentId": "null", "step": "null", "owner": "developer", "priority": "high",
            "createdAt": "2026-07-20 10:00", "updatedAt": "2026-07-20 10:00",
            "startedAt": "2026-07-20 10:00",
            "testingAt": "null", "reviewAt": "null", "doneAt": "null",
        }
        fm.update(overrides)
        return fm

    def test_reviewat_backfilled_in_review(self):
        import sync_properties as sp
        out, changes = sp.normalize_fields(self._fm("review"), "task-a", "demo", "review", True, None)
        self.assertNotIn(out["reviewAt"], (None, "", "null"))
        self.assertTrue(any("reviewAt" in c for c in changes))

    def test_testingat_backfilled_in_testing(self):
        import sync_properties as sp
        out, _ = sp.normalize_fields(self._fm("testing"), "task-a", "demo", "testing", True, None)
        self.assertNotIn(out["testingAt"], (None, "", "null"))

    def test_doneat_backfilled_in_done(self):
        import sync_properties as sp
        out, _ = sp.normalize_fields(self._fm("done"), "task-a", "demo", "done", True, None)
        self.assertNotIn(out["doneAt"], (None, "", "null"))

    def test_no_backfill_for_status_without_timestamp_field(self):
        import sync_properties as sp
        out, _ = sp.normalize_fields(self._fm("in-progress"), "task-a", "demo", "in-progress", True, None)
        self.assertEqual(out["testingAt"], "null")
        self.assertEqual(out["reviewAt"], "null")
        self.assertEqual(out["doneAt"], "null")

    def test_existing_timestamp_not_overwritten(self):
        import sync_properties as sp
        fm = self._fm("review", reviewAt="2026-07-19 08:00")
        out, _ = sp.normalize_fields(fm, "task-a", "demo", "review", True, None)
        self.assertEqual(out["reviewAt"], "2026-07-19 08:00")


# ---------------------------------------------------------------------------
# Test: compact role packets (move/resume default compact vs --full)
# ---------------------------------------------------------------------------

_SYNTH_ROLE_TEXT = (
    "## Чеклист\n"
    "- [ ] step one: `python scripts/kanban.py check .` inline stays\n"
    "python scripts/kanban.py move . x TODO\n"
    "`python scripts/kanban.py check .`\n"
    "\n"
    "```\n"
    "python scripts/kanban.py comment . x role \"hi\"\n"
    "```\n"
    "\n"
    "```\n"
    "WORKSPACE_ROOT: <path>\n"
    "Prompt template body is kept.\n"
    "```\n"
)


class TestCompactRolePackets(unittest.TestCase):
    """Regression coverage for the EXISTING compact/full packet behavior of
    move_card.py (compact = not args.full default) and resume.py
    (--full-checklist via role_prompt.print_role_checklist, compact default).
    Tests only — no behavior change (task compact-role-packets)."""

    # -- unit: filtering semantics on synthetic role text --------------------

    def test_compact_strips_python_command_surfaces(self):
        import move_card as mc
        out = mc._compact_text(_SYNTH_ROLE_TEXT)
        self.assertIn("step one", out)                     # checklist bullet kept
        self.assertNotIn("move . x TODO", out)             # bare python line stripped
        self.assertNotIn("`python scripts/kanban.py check .`\n", out + "\n")
        self.assertNotIn('comment . x role "hi"', out)     # python fence stripped

    def test_compact_keeps_non_python_fence(self):
        import move_card as mc
        out = mc._compact_text(_SYNTH_ROLE_TEXT)
        self.assertIn("WORKSPACE_ROOT: <path>", out)       # subagent prompt template kept
        self.assertIn("Prompt template body is kept.", out)

    def test_compact_parity_move_card_vs_role_prompt(self):
        import move_card as mc
        self.assertEqual(mc._compact_text(_SYNTH_ROLE_TEXT),
                         role_prompt.compact_text(_SYNTH_ROLE_TEXT))

    def test_compact_idempotent(self):
        import move_card as mc
        once = mc._compact_text(_SYNTH_ROLE_TEXT)
        self.assertEqual(mc._compact_text(once), once)

    # -- integration: move default (compact) vs --full -----------------------

    _workspace = staticmethod(TestStartStampTiming._workspace)

    @staticmethod
    def _move_capture(root, slug, column, extra=None):
        import io
        import contextlib
        import move_card as mc
        old_argv = sys.argv[:]
        buf = io.StringIO()
        try:
            sys.argv = (["move_card.py", str(root), slug, column, "--board", "demo.md"]
                        + (extra or []))
            with contextlib.redirect_stdout(buf):
                rc = mc.main()
        finally:
            sys.argv = old_argv
        return rc, buf.getvalue()

    def _to_todo(self, root):
        # BACKLOG -> TODO gate: startedAt must be stamped first (analyst rule).
        self.assertEqual(TestStartStampTiming._tags_start(root, "task-alpha"), 0)

    def test_move_default_compact_output_contract(self):
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            self._to_todo(root)
            rc, out = self._move_capture(root, "task-alpha", "TODO")
            self.assertEqual(rc, 0)
            self.assertIn("=== РОЛЬ:", out)
            self.assertIn("=== КОНЕЦ ЧЕКЛИСТА ===", out)    # marker survives compact
            self.assertIn("✅ task-alpha: BACKLOG → TODO", out)  # transition confirmation
            self.assertIn("=== RESUME PACKET ===", out)
            self.assertIn("Gate:", out)                       # gate info present
            # compact contract: no bare python command lines outside fences
            in_fence = False
            for line in out.splitlines():
                if line.startswith("```"):
                    in_fence = not in_fence
                    continue
                if not in_fence:
                    self.assertFalse(line.strip().startswith("python "),
                                     f"bare command line leaked into compact output: {line!r}")

    def test_move_full_flag_restores_command_lines(self):
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            self._to_todo(root)
            rc_c, out_compact = self._move_capture(root, "task-alpha", "TODO")
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            self._to_todo(root)
            rc_f, out_full = self._move_capture(root, "task-alpha", "TODO", extra=["--full"])
        self.assertEqual((rc_c, rc_f), (0, 0))
        self.assertIn("=== КОНЕЦ ЧЕКЛИСТА ===", out_full)
        self.assertIn("✅ task-alpha: BACKLOG → TODO", out_full)
        # full output is a superset rendering: never shorter than compact
        self.assertGreaterEqual(len(out_full.splitlines()), len(out_compact.splitlines()))

    def test_move_in_progress_compact_keeps_subagent_template(self):
        # developer.md holds the tester-subagent prompt in a non-python fence;
        # compact mode must keep it so a developer can still spawn subagents.
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            self._to_todo(root)
            rc, _ = self._move_capture(root, "task-alpha", "TODO")
            self.assertEqual(rc, 0)
            spec_path = tasks / "specs" / "task-alpha.md"
            spec_path.write_text(
                spec_path.read_text(encoding="utf-8").replace(
                    "## Comments\n",
                    "## Comments\n2026-07-05 00:00:00 | planner | ready\n",
                ),
                encoding="utf-8",
            )
            rc, out = self._move_capture(root, "task-alpha", "IN_PROGRESS")
            self.assertEqual(rc, 0)
            self.assertIn("WORKSPACE_ROOT:", out)
            self.assertIn("=== КОНЕЦ ЧЕКЛИСТА ===", out)

    # -- integration: resume --full-checklist ---------------------------------

    def test_resume_full_checklist_prints_role_checklist(self):
        import io
        import contextlib
        with tempfile.TemporaryDirectory() as td:
            root, tasks = self._workspace(td)
            self._to_todo(root)
            rc, _ = self._move_capture(root, "task-alpha", "TODO")
            self.assertEqual(rc, 0)
            old_argv = sys.argv[:]
            buf = io.StringIO()
            try:
                sys.argv = ["resume.py", str(root), "task-alpha", "--full-checklist",
                            "--board", "demo.md"]
                with contextlib.redirect_stdout(buf):
                    rc = resume.main()
            finally:
                sys.argv = old_argv
            out = buf.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("=== РОЛЬ:", out)
            self.assertIn("=== КОНЕЦ ЧЕКЛИСТА ===", out)
            self.assertIn("## Checklist", out)


# ---------------------------------------------------------------------------
# Test: set_item_type — scripted itemType mutation (standalone + update)
# ---------------------------------------------------------------------------


class TestSetItemType(unittest.TestCase):
    """`set-type` / `update --item-type` set frontmatter `itemType:` via one
    transform factory (DRY with the composite), validating against
    lb.VALID_ITEMTYPE. Replaces the last manual frontmatter edit (§8/§10)."""

    @staticmethod
    def _workspace(td, item_type="unassigned"):
        root = Path(td)
        specs = root / "tasks" / "specs"
        specs.mkdir(parents=True)
        (specs / "task-x.md").write_text(
            "---\n"
            "flowId: demo/task/task-x\n"
            f"itemType: {item_type}\n"
            "status: backlog\n"
            "parentId: null\n"
            "step: null\n"
            "owner: analyst\n"
            "priority: medium\n"
            "createdAt: 2026-07-14 10:00\n"
            "updatedAt: 2026-07-14 10:00\n"
            "reminder: null\n"
            "startedAt: null\n"
            "testingAt: null\n"
            "reviewAt: null\n"
            "doneAt: null\n"
            "dependsOn: []\n"
            "blocks: []\n"
            "---\n\n"
            "# 📋 Task X\n\n"
            "## Definition of Done (DoD)\n- [ ] Done\n\n"
            "## Changelog\n\n## Comments\n",
            encoding="utf-8",
        )
        return root, specs / "task-x.md"

    @staticmethod
    def _set_type(root, *extra_args):
        import set_item_type as sit
        old_argv = sys.argv[:]
        try:
            sys.argv = ["set_item_type.py", str(root), *extra_args]
            return sit.main()
        finally:
            sys.argv = old_argv

    @staticmethod
    def _update(root, *extra_args):
        import update as upd
        old_argv = sys.argv[:]
        try:
            sys.argv = ["update.py", str(root), *extra_args]
            return upd.main()
        finally:
            sys.argv = old_argv

    def test_set_type_task_epic_subtask_succeed(self):
        for value in ("task", "epic", "subtask"):
            with tempfile.TemporaryDirectory() as td:
                root, spec = self._workspace(td)
                self.assertEqual(self._set_type(root, "task-x", value), 0)
                text = spec.read_text(encoding="utf-8")
                self.assertIn(f"itemType: {value}", text)
                # updatedAt bumped away from the seeded value
                self.assertNotIn("updatedAt: 2026-07-14 10:00\n", text)

    def test_set_type_replaces_unassigned_with_task(self):
        with tempfile.TemporaryDirectory() as td:
            root, spec = self._workspace(td, item_type="unassigned")
            self.assertEqual(self._set_type(root, "task-x", "task"), 0)
            text = spec.read_text(encoding="utf-8")
            self.assertIn("itemType: task", text)
            self.assertNotIn("itemType: unassigned", text)

    def test_set_type_bogus_value_exits_1_without_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            root, spec = self._workspace(td)
            before = spec.read_text(encoding="utf-8")
            self.assertEqual(self._set_type(root, "task-x", "bogus"), 1)
            self.assertEqual(spec.read_text(encoding="utf-8"), before)

    def test_transform_factory_rejects_invalid_value(self):
        import set_item_type as sit
        with self.assertRaises(ku.MutationError) as ctx:
            sit.make_item_type_transform("task-x", "bogus")
        # error message lists the allowed values (DRY: from lb.VALID_ITEMTYPE)
        self.assertIn("task", str(ctx.exception))
        self.assertIn("epic", str(ctx.exception))

    def test_update_item_type_and_comment_in_one_call(self):
        with tempfile.TemporaryDirectory() as td:
            root, spec = self._workspace(td, item_type="unassigned")
            rc = self._update(root, "task-x", "--item-type", "epic",
                              "--comment", "classified as epic", "--as", "analyst")
            self.assertEqual(rc, 0)
            text = spec.read_text(encoding="utf-8")
            self.assertIn("itemType: epic", text)
            self.assertIn("classified as epic", text)

    def test_update_item_type_bogus_value_exits_1(self):
        with tempfile.TemporaryDirectory() as td:
            root, spec = self._workspace(td)
            before = spec.read_text(encoding="utf-8")
            self.assertEqual(self._update(root, "task-x", "--item-type", "bogus"), 1)
            self.assertEqual(spec.read_text(encoding="utf-8"), before)


# ---------------------------------------------------------------------------


class TestStaleUat(unittest.TestCase):
    """check_stale_uat measures staleness from updatedAt (last activity), fires on
    the >= threshold day, and only for status=uat cards. There is no `uatAt` field —
    no script writes one — so the reminder is intentionally activity-based."""

    @staticmethod
    def _spec(specs_dir, slug, status, updated_at):
        (specs_dir / f"{slug}.md").write_text(
            "---\n"
            f"status: {status}\n"
            f"updatedAt: {updated_at}\n"
            "---\n\n"
            f"# 📋 {slug}\n",
            encoding="utf-8",
        )

    def test_fires_on_threshold_day_and_only_for_uat(self):
        with tempfile.TemporaryDirectory() as td:
            specs = Path(td)
            today = dt.date(2026, 7, 16)
            self._spec(specs, "uat-2d", "uat", "2026-07-14 09:00:00")   # exactly 2 days → fires (>=)
            self._spec(specs, "uat-1d", "uat", "2026-07-15 09:00:00")   # 1 day → below threshold
            self._spec(specs, "review-old", "review", "2026-07-01 09:00:00")  # not uat → ignored
            stale = cr.check_stale_uat(specs, today, threshold_days=2)
            slugs = {s for s, _title, _days in stale}
            self.assertEqual(slugs, {"uat-2d"})
            days = {s: d for s, _t, d in stale}
            self.assertEqual(days["uat-2d"], 2)

    def test_recent_activity_resets_staleness(self):
        """A UAT card touched today is not stale — updatedAt is bumped by any mutation."""
        with tempfile.TemporaryDirectory() as td:
            specs = Path(td)
            today = dt.date(2026, 7, 16)
            self._spec(specs, "uat-fresh", "uat", "2026-07-16 09:00:00")
            self.assertEqual(cr.check_stale_uat(specs, today, threshold_days=2), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
