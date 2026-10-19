"""Kanban bridge to existing Claude-style JS Dynamic Workflows (Codex re-host).

This file intentionally DOES NOT implement agent scheduling, plan DAG, parallel,
pipeline, or replay. Upstream runner does those. We implement only Kanban
lifecycle integration, scoped approvals, run records and independent evidence.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

import dynamic_prepare as prepare
from dynamic_gate import artifact_digest, done_gate, journal_path, save_atomic


def within(workspace: Path, value: str) -> Path:
    path = (workspace / value).resolve()
    if not path.is_relative_to(workspace.resolve()) or not path.is_file():
        raise ValueError(f"File must exist inside workspace: {value}")
    if path.is_symlink():
        raise ValueError("Refuse symbolic-link input: " + value)
    return path


def run_external(command: list[str], cwd: Path, timeout: int):
    start = time.monotonic()
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=timeout)
        return (result.returncode, result.stdout[-250000:],
                result.stderr[-12000:], round(time.monotonic() - start, 3))
    except subprocess.TimeoutExpired as exc:
        return 124, "", f"Timeout after {timeout}s: {exc}", round(time.monotonic() - start, 3)
    except OSError as exc:
        return 127, "", str(exc), round(time.monotonic() - start, 3)


def pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


@contextmanager
def exclusive_run_lock(path: Path):
    """Protect workflow/result journal against concurrent runners; reclaim dead PIDs."""
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        try:
            pid = int(path.read_text(encoding="utf-8").splitlines()[0])
        except (ValueError, OSError, IndexError):
            raise ValueError(f"Workflow lock exists (unknown owner): {path}")
        if pid_alive(pid):
            raise ValueError(f"Workflow already running under PID {pid}")
        path.unlink(missing_ok=True)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(str(os.getpid()) + "\n")
    try:
        yield
    finally:
        path.unlink(missing_ok=True)


def resolved_inputs(workspace: Path, slug: str, args_path: str | None, workspace_write: bool):
    default = prepare.paths(workspace, slug)[1]
    filename = args_path if args_path else (str(default) if default.is_file() else None)
    data = {}
    inp_name = None
    inp_sha = None
    if filename:
        p = within(workspace, filename)
        inp_name = str(p.relative_to(workspace))
        inp_sha = artifact_digest(workspace, inp_name)
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("Workflow arguments must be a JSON object")
    # Do not trust a caller-supplied allowWrites flag; runner mode is authoritative.
    data["allowWrites"] = bool(workspace_write)
    return data, inp_name, inp_sha


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=[
        "doctor", "init", "plan", "run", "resume", "import-native", "verify", "status"])
    parser.add_argument("workspace")
    parser.add_argument("slug")
    parser.add_argument("--workflow", help="Reviewed *.workflow.js path inside project")
    parser.add_argument("--runner", default=os.environ.get("KANBAN_DYNAMIC_RUNNER"),
                        help="Pinned third-party runner/bin/run-workflow.js (or KANBAN_DYNAMIC_RUNNER)")
    parser.add_argument("--args-file", help="Optional JSON task input inside project (defaults to init-generated)")
    parser.add_argument("--approve-execution", action="store_true",
                        help="Explicit user approval for third-party runner and agents")
    parser.add_argument("--workspace-write", action="store_true",
                        help="Allow single-writer JS workflow to modify project files")
    parser.add_argument("--budget", type=int, default=1500000)
    parser.add_argument("--timeout", type=int, default=3600)
    parser.add_argument("--frontier", action="store_true", help="Pin to latest Codex frontier model")
    parser.add_argument("--model", help="Pin exact model name (cannot combine with --frontier)")
    parser.add_argument("--effort", choices=["none", "minimal", "low", "medium", "high", "xhigh"],
                        default="medium")
    parser.add_argument("--test-cmd", help="Independent test command (NO shell interpolation)")
    parser.add_argument("--artifact", action="append", default=[],
                        help="Relative output artifact; repeat for all claimed deliverables")
    parser.add_argument("--result-file", help="Native Claude Code workflow JSON return value")
    parser.add_argument("--overwrite", action="store_true", help="Regenerate reviewed template/inputs")
    args = parser.parse_args()
    workspace = Path(args.workspace).expanduser().resolve()
    tasks = workspace / "tasks"
    if not tasks.is_dir():
        parser.error("tasks/ directory is missing")
    if args.model and args.frontier:
        parser.error("--model and --frontier are mutually exclusive")
    if not (1 <= args.budget <= 20000000 and 1 <= args.timeout <= 86400):
        parser.error("budget (1..20M) or timeout (1..86400s) is out of range")
    try:
        record = journal_path(tasks, args.slug)
        upstream = record.parent.parent / "upstream" / (args.slug + ".jsonl")
        lock = record.parent.parent / "locks" / (args.slug + ".lock")

        if args.action == "doctor":
            runner = Path(args.runner).expanduser().resolve() if args.runner else None
            print(json.dumps(prepare.doctor(runner), ensure_ascii=False, indent=2))
            return 0
        if args.action == "init":
            print(json.dumps(prepare.init(workspace, args.slug, overwrite=args.overwrite),
                             ensure_ascii=False, indent=2))
            return 0
        if args.action == "status":
            if not record.is_file():
                print(json.dumps({"task":args.slug, "status":"not-started"}))
                return 0
            state = json.loads(record.read_text(encoding="utf-8"))
            verified, reason = done_gate(tasks, args.slug)
            print(json.dumps({"task":args.slug, "run":state.get("run"), "verification":state.get("verification"),
                              "done_gate":verified, "reason":reason,
                              "upstream_journal":str(upstream)}, ensure_ascii=False, indent=2))
            return 0

        if args.action in ("plan", "run", "resume", "import-native"):
            fallback = prepare.paths(workspace, args.slug)[0]
            workflow = within(workspace, args.workflow or str(fallback))
            workflow_name = str(workflow.relative_to(workspace))
            if not workflow.name.endswith(".workflow.js"):
                raise ValueError("Expected a reviewed *.workflow.js script")
            code_sha = artifact_digest(workspace, workflow_name)
            inputs, inp_name, inp_sha = resolved_inputs(
                workspace, args.slug, args.args_file,
                True if args.action == "plan" else args.workspace_write)
            if args.action != "plan" and not args.approve_execution:
                raise ValueError("Execution/import requires --approve-execution")
            if args.action == "import-native":
                if not args.result_file:
                    raise ValueError("Native import requires --result-file")
                payload = json.loads(within(workspace, args.result_file).read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("Native result must be a JSON object")
                approved = payload.get("approved") is True
                with exclusive_run_lock(lock):
                    state = {"version":1, "task":args.slug,
                             "run":{"status":"completed" if approved else "failed",
                                    "exit_code":0 if approved else 1, "approved":approved,
                                    "source":"native-import",
                                    "workflow":workflow_name, "workflow_sha256":code_sha,
                                    "inputs":inp_name, "inputs_sha256":inp_sha,
                                    "output":payload},
                             "verification":{"passed":False}}
                    save_atomic(record, state)
                print(json.dumps({"status":state["run"]["status"], "journal":str(record)}))
                return 0 if approved else 1

            runner = Path(args.runner).expanduser().resolve() if args.runner else None
            if not runner or not runner.is_file() or runner.name != "run-workflow.js":
                raise ValueError("Supply installed, reviewed runner via --runner or KANBAN_DYNAMIC_RUNNER")
            upstream.parent.mkdir(parents=True, exist_ok=True)
            cmd = ["node", str(runner), str(workflow), "--budget", str(args.budget),
                   "--sandbox", "workspace-write" if args.workspace_write else "read-only",
                   "--journal", str(upstream), "--args", json.dumps(inputs)]
            if args.frontier:
                cmd.append("--frontier")
            if args.model:
                cmd.extend(["--pin-model", args.model])
            cmd.extend(["--effort", args.effort])
            if args.action == "plan":
                cmd.append("--plan")
                rc, out, err, elapsed = run_external(cmd, workspace, args.timeout)
                print(json.dumps({"status":"planned" if rc == 0 else "failed", "exit_code":rc,
                                  "wall_seconds":elapsed, "stdout":out[-4000:],
                                  "stderr":err[-8000:]}, ensure_ascii=False))
                return 0 if rc == 0 else 1

            with exclusive_run_lock(lock):
                if args.action == "resume":
                    if not upstream.is_file() or not record.is_file():
                        raise ValueError("No previous run to resume; run first")
                    old = json.loads(record.read_text(encoding="utf-8")).get("run", {})
                    if old.get("workflow_sha256") != code_sha or old.get("inputs_sha256") != inp_sha:
                        raise ValueError("Workflow/inputs changed; start a new run instead of replaying stale results")
                    if old.get("sandbox") != ("workspace-write" if args.workspace_write else "read-only"):
                        raise ValueError("Sandbox mode changed; cannot reuse cached worker outputs")
                    cmd.append("--resume")
                else:
                    cmd.append("--fresh")
                # Mark running BEFORE launching to fail closed across crashes/timeout.
                state = {"version":1,"task":args.slug,
                         "run":{"status":"running", "exit_code":None,
                                "approved":None, "workflow":workflow_name,
                                "workflow_sha256":code_sha, "inputs":inp_name,
                                "inputs_sha256":inp_sha,
                                "sandbox":"workspace-write" if args.workspace_write else "read-only",
                                "budget":args.budget, "upstream_journal":str(upstream)},
                         "verification":{"passed":False}}
                save_atomic(record, state)
                rc, out, err, elapsed = run_external(cmd, workspace, args.timeout)
                try:
                    payload = json.loads(out.strip())
                    approved = isinstance(payload, dict) and payload.get("approved") is True
                except json.JSONDecodeError:
                    payload = None
                    approved = False
                if rc == 0 and not approved:
                    rc = 1
                    err += "\nWorkflow returned no explicit approved:true"
                state["run"].update({
                    "status":"completed" if rc == 0 else "failed",
                    "exit_code":rc, "approved":approved, "wall_seconds":elapsed,
                    "result":payload, "stderr_tail":err[-5000:]})
                save_atomic(record, state)
                print(json.dumps({"status":state["run"]["status"],"exit_code":rc,
                                  "wall_seconds":elapsed, "journal":str(record),
                                  "upstream_journal":str(upstream)}, ensure_ascii=False))
                return 0 if rc == 0 else 1

        if args.action == "verify":
            if not args.test_cmd or not args.artifact:
                raise ValueError("verify requires --test-cmd and at least one --artifact")
            with exclusive_run_lock(lock):
                if not record.exists():
                    raise ValueError("No workflow result; run/import first")
                state = json.loads(record.read_text(encoding="utf-8"))
                if state.get("run", {}).get("status") != "completed":
                    raise ValueError("Workflow incomplete; cannot verify")
                command = shlex.split(args.test_cmd, posix=os.name != "nt")
                if not command:
                    raise ValueError("Empty test command")
                # Invalidate previous verification before starting a potentially crashing test.
                state["verification"] = {"passed":False, "status":"running"}
                save_atomic(record, state)
                rc, out, err, elapsed = run_external(command, workspace, args.timeout)
                artifacts = {}
                if rc == 0:
                    for name in args.artifact:
                        p = within(workspace, name)
                        rel = str(p.relative_to(workspace))
                        artifacts[rel] = artifact_digest(workspace, rel)
                state["verification"] = {
                    "passed":rc == 0 and bool(artifacts), "status":"completed" if rc == 0 else "failed",
                    "exit_code":rc, "command":command, "wall_seconds":elapsed,
                    "stdout_tail":out[-4000:], "stderr_tail":err[-4000:],
                    "artifacts":artifacts}
                save_atomic(record, state)
                ok, reason = done_gate(tasks, args.slug)
                print(json.dumps({"passed":ok, "reason":reason, "journal":str(record)},
                                 ensure_ascii=False))
                return 0 if ok else 1
    except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
        print(f"dynamic workflow: {exc}", file=sys.stderr)
        return 1
    return 2


if __name__ == "__main__":
    sys.exit(main())
