"""Paired benchmark for real legacy vs dynamic Kanban executions.

Never treat harness unit tests or simulated runs as evidence of better model output.
Each row: task_id, repeat, variant, passed, wall_seconds, tokens,
          model, repo_sha, budget, evaluator_id, evidence_ref.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import statistics
import sys


def validate_evidence(row: dict) -> None:
    """Require real saved logs and a deterministic reconciliation of scored PASS."""
    root = Path(row.get("evidence_ref") or "")
    required = ("agent.stdout.txt", "agent.stderr.txt", "tests.stdout.txt",
                "tests.stderr.txt", "artifacts.json")
    if not root.is_dir() or any(not (root / name).is_file() for name in required):
        raise ValueError(f"raw evidence folder missing/incomplete: {root}")
    artifacts = json.loads((root / "artifacts.json").read_text(encoding="utf-8"))
    verified = artifacts.get("verified") or []
    missing = artifacts.get("missing") or []
    if not verified or not isinstance(verified, list) or not isinstance(missing, list):
        raise ValueError(f"no verified artifact hashes: {root}")
    for entry in verified:
        if not isinstance(entry.get("path"), str) or not isinstance(entry.get("sha256"), str) or len(entry["sha256"]) != 64:
            raise ValueError(f"bad artifact evidence: {root}")
    scored = row.get("agent_exit_code") == 0 and row.get("test_exit_code") == 0 and not missing
    if row.get("passed") is not scored:
        raise ValueError(f"success claim contradicts exit codes/artifacts: {root}")


def load_pairs(path: Path):
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_key: dict[tuple, dict] = defaultdict(dict)
    for row in rows:
        key = (str(row["task_id"]), int(row["repeat"]))
        arm = row["variant"]
        if arm not in ("legacy", "dynamic") or arm in by_key[key]:
            raise ValueError(f"invalid/duplicate variant at {key}: {arm}")
        if (not isinstance(row["passed"], bool) or not isinstance(row["tokens"], (int, float))
                or row["tokens"] < 0 or not isinstance(row["wall_seconds"], (int, float))
                or row["wall_seconds"] <= 0):
            raise ValueError(f"bad measurement: {key}/{arm}")
        validate_evidence(row)
        by_key[key][arm] = row
    if not by_key or any(set(pair) != {"legacy", "dynamic"} for pair in by_key.values()):
        raise ValueError("benchmark must have matched legacy/dynamic runs for every (task_id, repeat)")
    return list(by_key.values())


def ci95(values: list[float], rng: random.Random, samples=2000) -> list[float]:
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(samples))
    return [round(means[int(.025 * samples)], 4), round(means[int(.975 * samples)], 4)]


def summarize(pairs: list[dict]) -> dict:
    # Cluster by task: repeats of the same prompt are NOT independent observations.
    clustered = defaultdict(list)
    controls = ("model", "repo_sha", "budget", "evaluator_id", "evidence_ref")
    comparable = True
    for p in pairs:
        a, b = p["legacy"], p["dynamic"]
        for k in controls:
            if not a.get(k) or not b.get(k):
                comparable = False
        for k in ("model", "repo_sha", "budget", "evaluator_id"):
            if a.get(k) != b.get(k):
                comparable = False
        clustered[str(a["task_id"])].append(p)
    rng = random.Random(20261019)
    task_success, task_speed, task_tokens = [], [], []
    for task_pairs in clustered.values():
        task_success.append(statistics.mean(
            int(p["dynamic"]["passed"]) - int(p["legacy"]["passed"]) for p in task_pairs))
        task_speed.append(statistics.mean(
            (p["legacy"]["wall_seconds"] - p["dynamic"]["wall_seconds"])
            / p["legacy"]["wall_seconds"] for p in task_pairs))
        task_tokens.append(statistics.mean(
            (p["legacy"]["tokens"] - p["dynamic"]["tokens"])
            / max(1, p["legacy"]["tokens"]) for p in task_pairs))
    legacy_wins = sum(bool(p["legacy"]["passed"]) for p in pairs)
    dynamic_wins = sum(bool(p["dynamic"]["passed"]) for p in pairs)
    legacy_tokens = sum(p["legacy"]["tokens"] for p in pairs)
    dynamic_tokens = sum(p["dynamic"]["tokens"] for p in pairs)
    result = {
        "paired_runs": len(pairs),
        "unique_tasks": len(clustered),
        "controls_matched_and_evidence_present": comparable,
        "legacy_success": round(legacy_wins / len(pairs), 4),
        "dynamic_success": round(dynamic_wins / len(pairs), 4),
        "success_delta": round(statistics.mean(task_success), 4),
        "success_delta_ci95": ci95(task_success, rng),
        "mean_relative_speed_gain": round(statistics.mean(task_speed), 4),
        "mean_relative_speed_gain_ci95": ci95(task_speed, rng),
        "mean_relative_token_gain": round(statistics.mean(task_tokens), 4),
        "mean_relative_token_gain_ci95": ci95(task_tokens, rng),
        "tokens_per_verified_success": {
            "legacy": round(legacy_tokens / legacy_wins, 2) if legacy_wins else None,
            "dynamic": round(dynamic_tokens / dynamic_wins, 2) if dynamic_wins else None,
        },
    }
    minimum_sample = len(pairs) >= 30 and len(clustered) >= 20
    quality = result["success_delta_ci95"][0] > 0
    speed = result["mean_relative_speed_gain_ci95"][0] > 0
    tokens = result["mean_relative_token_gain_ci95"][0] > 0
    result["quality_and_speed_improved_confirmed"] = comparable and minimum_sample and quality and speed
    result["quality_and_token_efficiency_improved_confirmed"] = comparable and minimum_sample and quality and tokens
    result["note"] = ("Per-task cluster bootstrap (2000 resamples, descriptive 95% CI), "
                      "not an independently reviewed statistical study. Only real runs "
                      "with matched model/repo/budget/evaluator and evidence refs count "
                      "toward confirmation. Hold out evaluation tasks.")
    return result


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("measurements", type=Path, help="JSONL observations from REAL paired runs")
    args = ap.parse_args()
    try:
        print(json.dumps(summarize(load_pairs(args.measurements)), ensure_ascii=False, indent=2))
        return 0
    except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError) as err:
        print(f"evaluation rejected: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
