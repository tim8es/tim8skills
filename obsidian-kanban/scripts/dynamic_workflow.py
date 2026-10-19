"""Bridge to Claude Code's JS workflow shape via the standalone Codex re-host.

Uses the existing upstream runner; DOES NOT implement another agent scheduler.
The authored .workflow.js is always reviewed before an opt-in execution.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

from dynamic_gate import artifact_digest, done_gate, journal_path, save_atomic


def inside(workspace: Path, raw: str) -> Path:
    path = (workspace / raw).resolve()
    if not path.is_relative_to(workspace.resolve()) or not path.is_file():
        raise ValueError(f"file must exist inside workspace: {raw}")
    return path


def run_external(command: list[str], cwd: Path, timeout: int):
    start = time.monotonic()
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
        return result.returncode, result.stdout[-250000:], result.stderr[-12000:], round(time.monotonic() - start, 3)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 124 if isinstance(exc, subprocess.TimeoutExpired) else 127, "", str(exc), round(time.monotonic() - start, 3)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["plan", "run", "verify", "status"])
    parser.add_argument("workspace")
    parser.add_argument("slug")
    parser.add_argument("--workflow", help="reviewed .workflow.js path, inside workspace")
    parser.add_argument("--runner", help="path to external scasella runner/bin/run-workflow.js")
    parser.add_argument("--approve-execution", action="store_true",
                        help="explicit approval for executing JS and launching agents")
    parser.add_argument("--workspace-write", action="store_true",
                        help="allow agents to edit workspace (requires --approve-execution)")
    parser.add_argument("--budget", type=int, default=200000)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--test-cmd", help="independent executable test command (no shell)")
    parser.add_argument("--artifact", action="append", default=[], help="relative artifact path; repeat")
    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    tasks = workspace / "tasks"
    if not tasks.is_dir():
        parser.error("tasks/ folder missing")
    if not (1 <= args.budget <= 2000000) or not (1 <= args.timeout <= 14400):
        parser.error("budget/timeout outside allowed range")
    try:
        record = journal_path(tasks, args.slug)
        if args.action == "status":
            if not record.exists():
                print(json.dumps({"status": "not-started", "task": args.slug}))
                return 0
            state = json.loads(record.read_text(encoding="utf-8"))
            verified, reason = done_gate(tasks, args.slug)
            print(json.dumps({"run": state.get("run"), "verification": state.get("verification"),
                              "done_gate": verified, "reason": reason}, ensure_ascii=False))
            return 0
        if args.action in ("run", "plan"):
            if not args.runner or not args.workflow:
                parser.error("--runner and --workflow required")
            runner = Path(args.runner).expanduser().resolve()
            if not runner.is_file() or runner.name != "run-workflow.js":
                parser.error("--runner must point to existing run-workflow.js")
            workflow = inside(workspace, args.workflow)
            if workflow.suffix != ".js" or not workflow.name.endswith(".workflow.js"):
                parser.error("expected reviewed *.workflow.js")
            if args.action == "run" and not args.approve_execution:
                parser.error("run requires --approve-execution (review JS first)")
            if args.workspace_write and not args.approve_execution:
                parser.error("--workspace-write requires --approve-execution")
            sandbox = "workspace-write" if args.workspace_write else "read-only"
            command = ["node", str(runner), str(workflow), "--budget", str(args.budget),
                       "--sandbox", sandbox]
            if args.action == "plan":
                command.append("--plan")
            if args.action == "run":
                # Invalidate any previous PASS before invoking a potentially crashing runner.
                save_atomic(record, {"version": 1, "task": args.slug,
                    "run": {"status": "running", "workflow": str(workflow.relative_to(workspace)),
                            "workflow_sha256": artifact_digest(workspace, str(workflow.relative_to(workspace)))},
                    "verification": {"passed": False}})
            rc, out, err, elapsed = run_external(command, workspace, args.timeout)
            if args.action == "plan":
                print(json.dumps({"exit_code": rc, "wall_seconds": elapsed,
                                  "stdout": out[-8000:], "stderr": err[-3000:]}))
                return 0 if rc == 0 else 1
            try:
                payload = json.loads(out.strip())
                approved = payload.get("approved") if isinstance(payload, dict) else None
                if approved is not True or payload.get("success") is False or payload.get("status") == "failed":
                    rc = rc or 1
                    err += "\\nWorkflow has no explicit approved:true or reports failure."
            except (json.JSONDecodeError, AttributeError):
                approved = None
                # Some upstream output may be plain text; process success alone is insufficient.
                rc = rc or 1
                err += "\nWorkflow did not return JSON; no success evidence."
            state = {"version": 1, "task": args.slug,
                     "run": {"status": "completed" if rc == 0 and approved is True else "failed",
                             "exit_code": rc, "approved": approved,
                             "wall_seconds": elapsed, "workflow": str(workflow.relative_to(workspace)),
                             "workflow_sha256": artifact_digest(workspace, str(workflow.relative_to(workspace))),
                             "sandbox": sandbox, "budget": args.budget,
                             "stdout_tail": out[-4000:], "stderr_tail": err[-2000:]},
                     "verification": {"passed": False}}
            save_atomic(record, state)
            print(json.dumps({"status": state["run"]["status"], "exit_code": rc,
                              "wall_seconds": elapsed, "journal": str(record)}))
            return 0 if state["run"]["status"] == "completed" else 1

        if args.action == "verify":
            if not args.test_cmd or not args.artifact:
                parser.error("verify requires --test-cmd and >=1 --artifact")
            if not record.exists():
                parser.error("run evidence not found")
            state = json.loads(record.read_text(encoding="utf-8"))
            if state.get("run", {}).get("status") != "completed":
                parser.error("run is not complete; cannot verify")
            command = shlex.split(args.test_cmd, posix=os.name != "nt")
            if not command:
                parser.error("empty test command")
            rc, out, err, elapsed = run_external(command, workspace, args.timeout)
            artifacts = {}
            if rc == 0:
                for name in args.artifact:
                    inside(workspace, name)
                    artifacts[name] = artifact_digest(workspace, name)
            state["verification"] = {"passed": rc == 0 and bool(artifacts), "exit_code": rc,
                                     "command": command, "wall_seconds": elapsed,
                                     "stdout_tail": out[-4000:], "stderr_tail": err[-2000:],
                                     "artifacts": artifacts}
            save_atomic(record, state)
            passed, reason = done_gate(tasks, args.slug)
            print(json.dumps({"passed": passed, "reason": reason, "journal": str(record)}))
            return 0 if passed else 1
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"dynamic workflow error: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
