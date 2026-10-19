"""Offline integration and fault-injection tests; NO model-quality claims."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import contextlib
import io

SCRIPTS = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPTS))

import dynamic_gate as dg
import dynamic_eval as ev
import hooks
import move_card


class TestDynamicWorkflowGate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.tasks = self.root / "tasks"
        (self.tasks / "specs").mkdir(parents=True)
        (self.tasks / "specs" / "auth.md").write_text(
            "---\nworkflowMode: dynamic\nstatus: review\n---\n"
            "## Review Checklist\n- [x] checked\n## Comments\n", encoding="utf-8")
        (self.root / "artifact.txt").write_text("good", encoding="utf-8")
        (self.root / "dummy.workflow.js").write_text("//reviewed", encoding="utf-8")

    def state(self, **overrides):
        d = {"version": 1, "task": "auth",
             "run": {"status": "completed", "exit_code": 0, "approved": True,
                     "workflow": "dummy.workflow.js",
                     "workflow_sha256": dg.artifact_digest(self.root, "dummy.workflow.js")},
             "verification": {"passed": True, "exit_code": 0, "command": ["python", "-m", "unittest"],
                              "artifacts": {"artifact.txt": dg.artifact_digest(self.root, "artifact.txt")}}}
        d.update(overrides)
        dg.save_atomic(dg.journal_path(self.tasks, "auth"), d)

    def test_missing_evidence_blocks_done_even_with_checked_review(self):
        gate = hooks.before_move(self.tasks, "auth", "IN REVIEW", "DONE")
        self.assertFalse(gate.ok)
        self.assertIn("evidence missing", gate.message)

    def test_matching_independent_evidence_permits_done(self):
        self.state()
        gate = hooks.before_move(self.tasks, "auth", "IN REVIEW", "DONE")
        self.assertTrue(gate.ok, gate.message)

    def test_modified_workflow_script_blocks_done(self):
        self.state()
        (self.root / "dummy.workflow.js").write_text("//changed", encoding="utf-8")
        passed, reason = dg.done_gate(self.tasks, "auth")
        self.assertFalse(passed)
        self.assertIn("workflow script changed", reason)

    def test_stale_artifact_blocks_done(self):
        self.state()
        (self.root / "artifact.txt").write_text("changed", encoding="utf-8")
        ok, why = dg.done_gate(self.tasks, "auth")
        self.assertFalse(ok)
        self.assertIn("changed", why)

    def test_failed_or_unapproved_run_blocks_done(self):
        for run in (
            {"status": "failed", "exit_code": 1, "approved": True},
            {"status": "completed", "exit_code": 0, "approved": False},
        ):
            self.state(run=run)
            self.assertFalse(dg.done_gate(self.tasks, "auth")[0])

    def test_invalid_and_traversal_artifacts_rejected(self):
        with self.assertRaises(ValueError):
            dg.journal_path(self.tasks, "../escape")
        self.state()
        d = json.loads(dg.journal_path(self.tasks, "auth").read_text())
        d["verification"]["artifacts"] = {"../escape": "0" * 64}
        dg.save_atomic(dg.journal_path(self.tasks, "auth"), d)
        self.assertFalse(dg.done_gate(self.tasks, "auth")[0])

    def test_legacy_task_is_unaffected(self):
        (self.tasks / "specs" / "auth.md").write_text(
            "---\nstatus: review\n---\n## Review Checklist\n- [x] checked\n",
            encoding="utf-8")
        self.assertTrue(hooks.before_move(self.tasks, "auth", "IN REVIEW", "DONE").ok)


class TestRunnerBridge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "tasks").mkdir()
        (self.root / "artifact.txt").write_text("verified", encoding="utf-8")
        (self.root / "demo.workflow.js").write_text("// reviewed test workflow", encoding="utf-8")
        (self.root / "run-workflow.js").write_text(
            'const fs=require("fs"); const argv=process.argv;'
            'const i=argv.indexOf("--journal");'
            'if(i>=0){fs.mkdirSync(require("path").dirname(argv[i+1]),{recursive:true});'
            'fs.writeFileSync(argv[i+1],"");}'
            'if(argv.includes("--plan"))console.log(JSON.stringify({planned:true}));'
            'else console.log(JSON.stringify({approved:true,answer:"ok"}));',
            encoding="utf-8")

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPTS / "kanban.py"), "dynamic", *args],
            capture_output=True, text=True, timeout=20)

    def test_preflight_and_approved_run_then_verification(self):
        common = [str(self.root), "auth", "--runner", str(self.root / "run-workflow.js"),
                  "--workflow", "demo.workflow.js"]
        plan = self.cli("plan", *common)
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertFalse(dg.journal_path(self.root / "tasks", "auth").exists())
        denied = self.cli("run", *common)
        self.assertNotEqual(denied.returncode, 0)
        approved = self.cli("run", *common, "--approve-execution")
        self.assertEqual(approved.returncode, 0, approved.stderr)
        before = self.cli("status", str(self.root), "auth")
        self.assertFalse(json.loads(before.stdout)["done_gate"])
        verify = self.cli("verify", str(self.root), "auth",
                          "--test-cmd", f"{sys.executable} -c 'print(123)'",
                          "--artifact", "artifact.txt")
        self.assertEqual(verify.returncode, 0, verify.stderr)
        after = self.cli("status", str(self.root), "auth")
        self.assertTrue(json.loads(after.stdout)["done_gate"])

    def test_resume_uses_upstream_resume_switch(self):
        common = [str(self.root), "auth", "--runner", str(self.root / "run-workflow.js"),
                  "--workflow", "demo.workflow.js", "--approve-execution"]
        first = self.cli("run", *common)
        self.assertEqual(first.returncode, 0, first.stderr)
        resumed = self.cli("resume", *common)
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(json.loads(resumed.stdout)["status"], "completed")

    def test_no_fake_success_on_semantic_rejection(self):
        (self.root / "run-workflow.js").write_text(
            'console.log(JSON.stringify({approved:false}));', encoding="utf-8")
        cmd = ["run", str(self.root), "auth", "--runner", str(self.root / "run-workflow.js"),
               "--workflow", "demo.workflow.js", "--approve-execution"]
        result = self.cli(*cmd)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(dg.done_gate(self.root / "tasks", "auth")[0])


class TestPairedBenchmark(unittest.TestCase):
    def test_reject_incomplete_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "runs.jsonl"
            path.write_text(json.dumps({"task_id":"a","repeat":1,"variant":"legacy",
                                        "passed":True,"wall_seconds":1.0,"tokens":30}))
            with self.assertRaises(ValueError):
                ev.load_pairs(path)

    def test_equal_real_measurements_do_not_claim_improvement(self):
        pairs = []
        for i in range(35):
            legacy = {"task_id":f"t{i}", "repeat":0, "variant":"legacy",
                      "passed":True,"wall_seconds":1.0,"tokens":100}
            dynamic = {**legacy, "variant":"dynamic"}
            pairs.append({"legacy": legacy, "dynamic": dynamic})
        result = ev.summarize(pairs)
        self.assertFalse(result["quality_and_speed_improved_confirmed"])
        self.assertEqual(result["success_delta"], 0)
        self.assertFalse(result["controls_matched_and_evidence_present"])



class TestPartialMoveFailure(unittest.TestCase):
    def test_partial_board_spec_transition_is_failure_even_when_retried(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tasks = root / "tasks"
            (tasks / "specs").mkdir(parents=True)
            columns = ["BACKLOG", "ICEBOX", "TODO", "IN PROGRESS", "BLOCKED",
                       "TESTING", "IN REVIEW", "UAT", "REJECTED", "REWORK", "DONE"]
            board = "---\nkanban-plugin: board\n---\n\n"
            for column in columns:
                board += f"## {column}\n\n"
                if column == "BACKLOG":
                    board += "- [ ] [[auth|Auth]]\n\t➕ 2026-10-19\n\n"
            board += "%% kanban:settings\n{}\n%%\n"
            (tasks / "demo.md").write_text(board, encoding="utf-8")
            (tasks / "specs" / "auth.md").write_text(
                "---\nstatus: backlog\nstartedAt: 2026-10-19\n---\n"
                "## Changelog\n\n## Comments\n", encoding="utf-8")
            def invoke():
                prior = sys.argv[:]
                try:
                    sys.argv = ["move_card.py", str(root), "auth", "TODO",
                                "--board", "demo.md"]
                    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                        return move_card.main()
                finally:
                    sys.argv = prior
            with patch.object(move_card, "sync_spec_status", side_effect=OSError("injected failure")):
                self.assertEqual(invoke(), 1)
            self.assertEqual(invoke(), 1)  # board is TODO; spec is still BACKLOG
            self.assertEqual(hooks._frontmatter_value(
                (tasks / "specs" / "auth.md").read_text(encoding="utf-8"), "status"), "backlog")


class TestWorkflowPreparation(unittest.TestCase):
    def test_init_creates_real_template_inputs_and_opt_in_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = root / "tasks" / "specs"
            specs.mkdir(parents=True)
            spec = specs / "change.md"
            spec.write_text("---\nstatus: backlog\n---\n"
                            "# DEV: Change button\n"
                            "## Definition of Done (DoD)\n"
                            "- [ ] Button changes color on click\n"
                            "- [ ] Existing tests pass\n"
                            "## Changelog\n", encoding="utf-8")
            from dynamic_prepare import init, paths
            result = init(root, "change")
            self.assertEqual(result["status"], "initialized")
            wf, inputs = paths(root, "change")
            self.assertTrue(wf.is_file())
            self.assertTrue(inputs.is_file())
            self.assertIn("workflowMode: dynamic", spec.read_text())
            payload = json.loads(inputs.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["acceptance"]), 2)
            self.assertEqual(init(root, "change")["status"], "already-initialized")
            with self.assertRaises(ValueError):
                init(root, "../bad")

    def test_init_refuses_missing_dod(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            specs = root / "tasks" / "specs"
            specs.mkdir(parents=True)
            (specs / "x.md").write_text("---\nstatus: backlog\n---\n# Task\n")
            from dynamic_prepare import init
            with self.assertRaises(ValueError):
                init(root, "x")

    def test_different_inputs_invalidate_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "tasks").mkdir()
            (root / "sample.workflow.js").write_text("return {approved:true}", encoding="utf-8")
            (root / "inputs.json").write_text('{"task":"first"}', encoding="utf-8")
            runner = root / "run-workflow.js"
            runner.write_text(
                'const fs=require("fs");let a=process.argv,i=a.indexOf("--journal");'
                'if(i>=0){fs.mkdirSync(require("path").dirname(a[i+1]),{recursive:true});'
                'fs.writeFileSync(a[i+1],"");}'
                'console.log(JSON.stringify({approved:true}));', encoding="utf-8")
            common = [sys.executable,str(SCRIPTS / "kanban.py"),"dynamic"]
            options = [str(root),"x","--workflow","sample.workflow.js","--runner",str(runner),
                       "--args-file","inputs.json","--approve-execution"]
            p = subprocess.run(common + ["run"] + options, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            (root / "inputs.json").write_text('{"task":"second"}', encoding="utf-8")
            p = subprocess.run(common + ["resume"] + options, capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertIn("changed", p.stderr)

if __name__ == "__main__":
    unittest.main()
