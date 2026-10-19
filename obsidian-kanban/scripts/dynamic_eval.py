"""Paired benchmark for legacy vs dynamic Kanban agent execution.

Input JSONL: task_id, repeat, variant, passed, wall_seconds, tokens.
Never substitutes simulated runs for end-to-end model evaluation.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import statistics
import sys


def load_pairs(path: Path):
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    by_key: dict[tuple, dict] = defaultdict(dict)
    for row in rows:
        key = (str(row["task_id"]), int(row["repeat"]))
        arm = row["variant"]
        if arm not in ("legacy", "dynamic") or arm in by_key[key]:
            raise ValueError(f"invalid/duplicate variant at {key}: {arm}")
        if not isinstance(row["passed"], bool) or not (0 <= row["tokens"]) or not (0 < row["wall_seconds"]):
            raise ValueError(f"bad measurement: {key}/{arm}")
        by_key[key][arm] = row
    if not by_key or any(set(pair) != {"legacy", "dynamic"} for pair in by_key.values()):
        raise ValueError("benchmark must have matched legacy/dynamic runs for every (task_id, repeat)")
    return list(by_key.values())


def ci95(values: list[float], rng: random.Random, samples=2000) -> list[float]:
    n = len(values)
    means = sorted(sum(rng.choice(values) for _ in range(n)) / n for _ in range(samples))
    return [round(means[int(.025 * samples)], 4), round(means[int(.975 * samples)], 4)]


def summarize(pairs: list[dict]) -> dict:
    rng = random.Random(20261019)
    delta_success = [int(p["dynamic"]["passed"]) - int(p["legacy"]["passed"]) for p in pairs]
    speed_gain = [(p["legacy"]["wall_seconds"] - p["dynamic"]["wall_seconds"]) /
                  p["legacy"]["wall_seconds"] for p in pairs]
    token_gain = [(p["legacy"]["tokens"] - p["dynamic"]["tokens"]) /
                  max(1, p["legacy"]["tokens"]) for p in pairs]
    outcome = {
        "paired_runs": len(pairs),
        "unique_tasks": len({p["legacy"]["task_id"] for p in pairs}),
        "legacy_success": round(statistics.mean(int(p["legacy"]["passed"]) for p in pairs), 4),
        "dynamic_success": round(statistics.mean(int(p["dynamic"]["passed"]) for p in pairs), 4),
        "success_delta": round(statistics.mean(delta_success), 4),
        "success_delta_ci95": ci95(delta_success, rng),
        "mean_relative_speed_gain": round(statistics.mean(speed_gain), 4),
        "mean_relative_speed_gain_ci95": ci95(speed_gain, rng),
        "mean_relative_token_gain": round(statistics.mean(token_gain), 4),
        "mean_relative_token_gain_ci95": ci95(token_gain, rng),
    }
    # Minimum sample gate is conservative, not a guarantee of sufficient power.
    outcome["quality_and_speed_improved_confirmed"] = (
        len(pairs) >= 30
        and outcome["unique_tasks"] >= 20
        and outcome["success_delta_ci95"][0] > 0
        and outcome["mean_relative_speed_gain_ci95"][0] > 0
    )
    outcome["note"] = ("Paired bootstrap CIs over runs; repeat correlations within tasks may "
                       "make these optimistic. Randomize order, reserve unseen tasks, "
                       "use same models/budgets and independent hidden tests.")
    return outcome


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
