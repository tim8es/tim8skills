"""Reproducible, paired Codex-vs-Claude-style Kanban eval runner.

Runs REAL authenticated agents when --execute is given. No model call or
measurement is simulated. Agent CLI outputs and test logs remain inspectable.
The baseline is a single Codex agent instructed to use Kanban SKILL.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shlex
import subprocess
import sys
import tempfile
import time

from dynamic_prepare import init
from dynamic_gate import artifact_digest
from dynamic_workflow import run_external


def git(repo: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True, timeout=30)
    if p.returncode:
        raise RuntimeError(f"git {args}: {p.stderr[-1500:]}")
    return p.stdout.strip()


def parse_codex_tokens(jsonl: str) -> int | None:
    # The current Codex CLI emits turn.completed {usage:{input_tokens,output_tokens}}.
    # Prefer last cumulative usage; avoid double counting per-event repeat totals.
    best = None
    for line in jsonl.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "turn.completed":
            continue
        u = event.get("usage") or {}
        if isinstance(u.get("total_tokens"), (int, float)):
            best = int(u["total_tokens"])
        elif isinstance(u.get("input_tokens"), (int, float)) and isinstance(u.get("output_tokens"), (int, float)):
            best = int(u["input_tokens"] + u["output_tokens"])
    return best


def upstream_tokens(runner: Path, journal: Path) -> int | None:
    exe = runner.parent / "summarize-run.js"
    if not journal.is_file() or not exe.is_file():
        return None
    rc, out, _err, _elapsed = run_external(
        ["node", str(exe), "--journal", str(journal), "--json"], journal.parent, 30)
    if rc:
        return None
    try:
        metrics = json.loads(out).get("metrics", {})
        if not metrics.get("hasMetrics"):
            return None
        tokens = metrics.get("totalTokens")
        return int(tokens) if isinstance(tokens, (float, int)) else None
    except (ValueError, TypeError, AttributeError):
        return None


def snapshot(task: dict, workspace: Path, slug: str):
    # Benchmark tasks never modify the source checkout. A temporary Kanban spec
    # allows the same task contract to reach the dynamic bridge.
    specs = workspace / "tasks" / "specs"
    specs.mkdir(parents=True, exist_ok=True)
    spec = specs / f"{slug}.md"
    if spec.exists():
        raise ValueError("Benchmark slug collision: " + slug)
    items = "\n".join("- [ ] " + str(x).replace("\n", " ") for x in task["acceptance"])
    spec.write_text("---\nflowId: benchmark/task/" + slug + "\nstatus: backlog\n"
                    "owner: user\n---\n\n# " + str(task["prompt"]).replace("\n", " ") +
                    "\n\n## Definition of Done (DoD)\n" + items +
                    "\n\n## Comments\n\n## Changelog\n", encoding="utf-8")


def run_case(task: dict, arm: str, number: int, *, repo: Path, sha: str,
             runner: Path, model: str, budget: int, timeout: int,
             output_dir: Path, bridge: Path) -> dict:
    task_id = str(task["id"])
    slug = "bench-" + re.sub("[^a-zA-Z0-9_-]", "-", task_id)[:80]
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="kanban-eval-") as tmp:
        root = Path(tmp)
        workspace = root / "work"
        git(repo, "worktree", "add", "--detach", str(workspace), sha)
        try:
            snapshot(task, workspace, slug)
            prompt = str(task["prompt"]) + "\nAcceptance criteria:\n" + "\n".join(
                "- " + str(x) for x in task["acceptance"])
            record_dir = output_dir / task_id / str(number) / arm
            record_dir.mkdir(parents=True, exist_ok=True)
            rc = 1
            stdout, stderr, secs = "", "", 0.0
            tokens = None
            if arm == "legacy":
                # Explicitly use the Kanban skill when evaluating this repository.
                legacy = task.get("legacy_instruction",
                                  "Use obsidian-kanban/SKILL.md and its existing role protocol. "
                                  "Follow the process; do not use dynamic workflow commands.")
                cmd = ["codex", "exec", "--json", "--full-auto", "--model", model,
                       prompt + "\n" + legacy]
                rc, stdout, stderr, secs = run_external(cmd, workspace, timeout)
                tokens = parse_codex_tokens(stdout)
            else:
                init(workspace, slug)
                wf, _inputs = (
                    workspace / "tasks" / ".dynamic-workflows" / "scripts" / (slug + ".workflow.js"),
                    workspace / "tasks" / ".dynamic-workflows" / "inputs" / (slug + ".json"),
                )
                cmd = [sys.executable, str(bridge), "dynamic", "run", str(workspace), slug,
                       "--workflow", str(wf), "--runner", str(runner),
                       "--model", model, "--workspace-write", "--approve-execution",
                       "--budget", str(budget), "--timeout", str(timeout)]
                rc, stdout, stderr, secs = run_external(cmd, workspace, timeout + 60)
                journal = workspace / "tasks" / ".dynamic-workflows" / "upstream" / (slug + ".jsonl")
                tokens = upstream_tokens(runner, journal)
                # Keep a stable raw evidence snapshot before the worktree is deleted.
                if journal.exists():
                    (record_dir / "upstream.jsonl").write_bytes(journal.read_bytes())
                result_path = workspace / "tasks" / ".dynamic-workflows" / "runs" / (slug + ".json")
                if result_path.exists():
                    (record_dir / "run.json").write_bytes(result_path.read_bytes())

            test_cmd = shlex.split(task["test_cmd"], posix=os.name != "nt")
            if not test_cmd:
                raise ValueError("Empty hidden acceptance test command")
            test_rc, test_out, test_err, test_secs = run_external(test_cmd, workspace, timeout)
            verified_artifacts = []
            missing_artifacts = []
            for p in task["artifacts"]:
                try:
                    verified_artifacts.append({"path":p,"sha256":artifact_digest(workspace,p)})
                except (ValueError, OSError):
                    missing_artifacts.append(p)
            success = rc == 0 and test_rc == 0 and not missing_artifacts
            (record_dir / "agent.stdout.txt").write_text(stdout, encoding="utf-8")
            (record_dir / "agent.stderr.txt").write_text(stderr, encoding="utf-8")
            (record_dir / "tests.stdout.txt").write_text(test_out, encoding="utf-8")
            (record_dir / "tests.stderr.txt").write_text(test_err, encoding="utf-8")
            (record_dir / "artifacts.json").write_text(json.dumps(
                {"verified":verified_artifacts,"missing":missing_artifacts},indent=2))
            return {
                "task_id":task_id, "repeat":number,"variant":arm,
                "passed":success, "wall_seconds":round(time.monotonic()-start,3),
                "tokens":tokens, "model":model, "repo_sha":sha, "budget":budget,
                "evaluator_id":hashlib.sha256(task["test_cmd"].encode()).hexdigest()[:12],
                "evidence_ref":str(record_dir.resolve()),
                "agent_exit_code":rc, "test_exit_code":test_rc,
                "missing_artifacts":missing_artifacts, "agent_seconds":secs,
                "test_seconds":test_secs,
            }
        finally:
            git(repo, "worktree", "remove", "--force", str(workspace))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("manifest", type=Path)
    ap.add_argument("--runner", type=Path, required=True,
                    help="Pinned external runner/bin/run-workflow.js")
    ap.add_argument("--model", required=True, help="Same exact Codex model for both arms")
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--budget", type=int, default=1500000)
    ap.add_argument("--timeout", type=int, default=3600)
    ap.add_argument("--out", type=Path, default=Path("kanban-eval-output"))
    ap.add_argument("--execute", action="store_true",
                    help="Required to spend tokens and run agents against Git worktrees")
    args = ap.parse_args()
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        repo = (args.manifest.parent / manifest["repo"]).resolve()
        sha = git(repo, "rev-parse", (manifest.get("ref") or "HEAD") + "^{commit}")
        cases = manifest["tasks"]
        if not isinstance(cases, list) or not cases:
            raise ValueError("manifest must provide nonempty tasks list")
        for c in cases:
            if not c.get("id") or not c.get("prompt") or not c.get("acceptance") or not c.get("test_cmd") or not c.get("artifacts"):
                raise ValueError("Each task requires id/prompt/acceptance/test_cmd/artifacts")
        if not (1 <= args.repeat <= 10 and 1 <= args.budget <= 20000000 and 1 <= args.timeout <= 86400):
            raise ValueError("invalid repeat, budget or timeout")
        runner = args.runner.expanduser().resolve()
        if runner.name != "run-workflow.js" or not runner.is_file():
            raise ValueError("runner does not point to installed run-workflow.js")
        planned = {"repo":str(repo),"sha":sha,"model":args.model,
                   "tasks":len(cases),"repeats":args.repeat,
                   "total_agent_runs":2 * len(cases) * args.repeat,
                   "budget_each_dynamic":args.budget,
                   "mode":"execute" if args.execute else "dry-run",
                   "warning":"Legacy Codex CLI does not enforce the same token cap. Compare observed tokens."}
        print(json.dumps(planned,ensure_ascii=False,indent=2))
        if not args.execute:
            return 0
        bridge = Path(__file__).resolve().parent / "kanban.py"
        out = args.out.expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        file = out / "results.jsonl"
        rng = random.Random(19)
        jobs = [(task, rep, arm) for task in cases for rep in range(args.repeat)
                for arm in ("legacy","dynamic")]
        # Randomize order globally, but keep pairing by task+repeat.
        rng.shuffle(jobs)
        with file.open("w",encoding="utf-8") as sink:
            for task,rep,arm in jobs:
                result = run_case(task, arm, rep, repo=repo, sha=sha, runner=runner,
                                  model=args.model, budget=args.budget, timeout=args.timeout,
                                  output_dir=out, bridge=bridge)
                sink.write(json.dumps(result,ensure_ascii=False)+"\n")
                sink.flush()
                print(json.dumps({"task":task["id"],"repeat":rep,"arm":arm,
                                  "passed":result["passed"],"tokens":result["tokens"]}))
        print("Result JSONL:", file)
        print("Run kanban.py dynamic-eval",file)
        return 0
    except (OSError, ValueError, KeyError, RuntimeError, json.JSONDecodeError,
            subprocess.TimeoutExpired) as exc:
        print(f"benchmark: {exc}",file=sys.stderr)
        return 1


if __name__=="__main__":
    sys.exit(main())
