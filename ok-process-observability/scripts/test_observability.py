"""Deterministic tests for the process-observability scripts.

Builds a temporary kanban-like workspace and asserts context-cost rows.
Run: python .agents/skills/process-observability/scripts/test_observability.py
"""

from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import context_metrics
import observe

SPEC_TEMPLATE = """---
flowId: {project}/task/{slug}
itemType: task
status: ready
---

# DEV:{slug}

## Description
Body text.

## Changelog

2026-07-09 10:00:00 | analyst | Task created

## Comments

2026-07-09 10:01:00 | analyst | {comment}
"""


def build_workspace(root: Path) -> None:
    tasks = root / "tasks"
    specs = tasks / "specs"
    specs.mkdir(parents=True)
    (tasks / "alpha.md").write_text("## TODO\n\n- [ ] [[a-one|DEV:a-one]]\n", encoding="utf-8")
    (tasks / "beta.md").write_text("## TODO\n\n- [ ] [[b-one|DEV:b-one]]\n" * 3, encoding="utf-8")
    (specs / "a-one.md").write_text(
        SPEC_TEMPLATE.format(project="alpha", slug="a-one", comment="plain note"),
        encoding="utf-8",
    )
    (specs / "a-two.md").write_text(
        SPEC_TEMPLATE.format(
            project="alpha", slug="a-two", comment="!!!ВНИМАНИЕ!!! critical directive"
        ),
        encoding="utf-8",
    )
    (specs / "b-one.md").write_text(
        SPEC_TEMPLATE.format(project="beta", slug="b-one", comment="beta note"),
        encoding="utf-8",
    )


class ContextMetricsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        build_workspace(self.root)
        self.tasks = self.root / "tasks"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_unscoped_counts_all_boards_and_specs(self) -> None:
        data = context_metrics.collect(self.tasks)
        self.assertEqual(len(data["boards"]), 2)
        self.assertEqual(len(data["tasks"]), 3)
        self.assertEqual(sum(t["attention_count"] for t in data["tasks"]), 1)

    def test_board_scope_filters_specs_and_boards(self) -> None:
        data = context_metrics.collect(self.tasks, board="alpha.md")
        self.assertEqual([name for name, _ in data["boards"]], ["alpha.md"])
        self.assertEqual(sorted(t["slug"] for t in data["tasks"]), ["a-one", "a-two"])

    def test_project_scope_equals_board_scope(self) -> None:
        by_board = context_metrics.collect(self.tasks, board="beta.md")
        by_project = context_metrics.collect(self.tasks, project="beta")
        self.assertEqual(by_board["boards"], by_project["boards"])
        self.assertEqual(by_board["tasks"], by_project["tasks"])

    def test_board_and_project_together_is_error(self) -> None:
        with self.assertRaises(context_metrics.ScopeError):
            context_metrics.collect(self.tasks, board="alpha.md", project="beta")

    def test_board_file_sizes_reported(self) -> None:
        data = context_metrics.collect(self.tasks)
        sizes = dict(data["boards"])
        self.assertEqual(sizes["alpha.md"], (self.tasks / "alpha.md").stat().st_size)
        self.assertEqual(sizes["beta.md"], (self.tasks / "beta.md").stat().st_size)

    def test_comment_and_changelog_volume_positive(self) -> None:
        data = context_metrics.collect(self.tasks, project="alpha")
        for t in data["tasks"]:
            self.assertGreater(t["comments_bytes"], 0, t["slug"])
            self.assertGreater(t["changelog_bytes"], 0, t["slug"])
            self.assertGreater(t["spec_bytes"], 0, t["slug"])

    def test_render_rows_deterministic(self) -> None:
        out1 = context_metrics.render(context_metrics.collect(self.tasks, project="alpha"))
        out2 = context_metrics.render(context_metrics.collect(self.tasks, project="alpha"))
        self.assertEqual(out1, out2)
        self.assertIn("context-cost scope: alpha", out1)
        self.assertIn("specs scanned: 2", out1)
        self.assertIn("attention flags: 1", out1)
        self.assertIn("board alpha.md:", out1)

    def test_cli_main_exit_codes(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(context_metrics.main([str(self.root), "--board", "alpha.md"]), 0)
            self.assertEqual(context_metrics.main([str(self.root / "nope")]), 1)

    def test_observe_dispatcher(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(observe.main(["metrics", str(self.root), "--project", "beta"]), 0)
            self.assertEqual(observe.main(["unknown-cmd"]), 2)
            self.assertEqual(observe.main([]), 0)

    def test_read_only_no_mutation(self) -> None:
        before = {
            p: p.read_bytes() for p in sorted(self.tasks.rglob("*.md"))
        }
        with contextlib.redirect_stdout(io.StringIO()):
            context_metrics.main([str(self.root)])
        after = {
            p: p.read_bytes() for p in sorted(self.tasks.rglob("*.md"))
        }
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
