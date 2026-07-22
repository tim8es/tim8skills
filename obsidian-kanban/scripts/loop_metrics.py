#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""loop_metrics.py — read-only KPI snapshot for autonomous kanban loop.

Usage:
    python <SCRIPT_PREFIX>/loop_metrics.py <WORKSPACE_ROOT>

The command prints markdown and never writes files.
"""
from __future__ import annotations

import argparse
import datetime as dt
from pathlib import Path
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import lint_board as lb

ACTIVE_STATUSES = {"in-progress", "testing", "review", "rework", "blocked"}


class ScopeError(ValueError):
    pass


def project_from_flow_id(fm: dict) -> str | None:
    flow_id = (fm.get("flowId") or "").strip()
    return flow_id.split("/", 1)[0] if "/" in flow_id else None


def normalize_board_name(board: str) -> str:
    return board if board.endswith(".md") else f"{board}.md"


def scope_label(board: str | None = None, project: str | None = None) -> str:
    if board:
        return f"board {normalize_board_name(board)}"
    if project:
        return f"project {project}"
    return "all boards"


def resolve_scope(tasks: Path, *, board: str | None = None, project: str | None = None) -> tuple[set[str] | None, set[str] | None, str]:
    if board and project:
        raise ScopeError("Use only one scope: --board or --project")
    if board:
        board_name = normalize_board_name(board)
        board_path = tasks / board_name
        if not board_path.is_file():
            raise ScopeError(f"Board not found: {board_name}")
        return {board_name}, {board_path.stem}, scope_label(board=board_name)
    if project:
        board_path = tasks / f"{project}.md"
        if not board_path.is_file():
            raise ScopeError(f"Project board not found: {project}.md")
        return {board_path.name}, {project}, scope_label(project=project)
    return None, None, scope_label()


def read_specs(tasks: Path, projects: set[str] | None = None) -> tuple[dict[str, dict], dict[str, str]]:
    specs, bodies = {}, {}
    specs_dir = tasks / "specs"
    if not specs_dir.is_dir():
        return specs, bodies
    for md in sorted(specs_dir.glob("*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        fm = lb.parse_frontmatter(text)
        if fm is not None:
            if projects is not None and project_from_flow_id(fm) not in projects:
                continue
            specs[md.stem] = fm
            bodies[md.stem] = text
    return specs, bodies


def read_board(tasks: Path, board_names: set[str] | None = None, projects: set[str] | None = None) -> tuple[dict[str, str], int]:
    board, board_count = {}, 0
    for md in sorted(tasks.glob("*.md")):
        if md.name == "SKILL.md" or md.stem.endswith("-archive"):
            continue
        if board_names is not None and md.name not in board_names:
            continue
        if projects is not None and md.stem not in projects:
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        if "kanban-plugin: board" in text:
            board_count += 1
            board.update(lb.parse_board(text))
    for arc in sorted(tasks.glob("*-archive.md")):
        project = arc.stem[:-8]
        if projects is not None and project not in projects:
            continue
        if board_names is not None and f"{project}.md" not in board_names:
            continue
        text = arc.read_text(encoding="utf-8", errors="replace")
        if "kanban-plugin: board" in text:
            for slug in lb.parse_board(text):
                board.setdefault(slug, "DONE")
    return board, board_count


def lint_snapshot(tasks: Path, board: dict[str, str], specs: dict[str, dict], bodies: dict[str, str],
                  board_names: set[str] | None = None, projects: set[str] | None = None) -> lb.Report:
    rep = lb.Report()
    for md in sorted(tasks.glob("*.md")):
        if md.name == "SKILL.md" or md.stem.endswith("-archive"):
            continue
        if board_names is not None and md.name not in board_names:
            continue
        if projects is not None and md.stem not in projects:
            continue
        text = md.read_text(encoding="utf-8", errors="replace")
        if "kanban-plugin: board" in text:
            lb.lint_board_file(md, text, rep)
    lb.cross_checks(board, specs, bodies, rep, tasks_dir=tasks)
    return rep


def history_chain_score(specs: dict[str, dict], bodies: dict[str, str]) -> tuple[int, int, float]:
    done = [slug for slug, fm in specs.items() if fm.get("status") == "done"]
    if not done:
        return 0, 0, 0.0
    complete = 0
    for slug in done:
        hist = lb.extract_section(bodies.get(slug, ""), "Changelog", "История изменений")
        # Same finals logic as lint_board.py: a legal UAT path
        # (IN REVIEW → UAT → DONE) counts as a complete chain, not just the
        # direct IN REVIEW → DONE final.
        base_complete = all(step in hist for step in lb.DONE_CHAIN_BASE)
        has_valid_final = any(all(s in hist for s in finals) for finals in lb.DONE_CHAIN_FINALS)
        if base_complete and has_valid_final:
            complete += 1
    return complete, len(done), complete / len(done)


def categorize(rep: lb.Report) -> dict[str, int]:
    out = {
        "errors": rep.errors,
        "warnings": rep.warns,
        "orphan_backlog_icebox": 0,
        "orphan_todo_plus": 0,
        "research_routing": 0,
        "done_history_chain": 0,
        "done_overflow": 0,
    }
    for sev, _scope, msg in rep.items:
        if "orphan link" in msg:
            if sev == "ERROR":
                out["orphan_todo_plus"] += 1
            else:
                out["orphan_backlog_icebox"] += 1
        if "research-like" in msg:
            out["research_routing"] += 1
        if "DONE without a full history chain" in msg:
            out["done_history_chain"] += 1
        if "the DONE column has" in msg:
            out["done_overflow"] += 1
    return out


def metric_rows(tasks: Path, *, board: str | None = None, project: str | None = None) -> list[tuple[str, str, str, str]]:
    board_names, projects, _label = resolve_scope(tasks, board=board, project=project)
    board_map, board_count = read_board(tasks, board_names, projects)
    specs, bodies = read_specs(tasks, projects)
    rep = lint_snapshot(tasks, board_map, specs, bodies, board_names, projects)
    cats = categorize(rep)
    active = sum(1 for fm in specs.values() if fm.get("status") in ACTIVE_STATUSES)
    complete, total_done, ratio = history_chain_score(specs, bodies)
    todo_plus_orphans = cats["orphan_todo_plus"]
    rows = [
        ("lint errors", str(cats["errors"]), "0", "Hard gate for autonomous transitions."),
        ("lint warnings", str(cats["warnings"]), "trend down", "Existing debt plus process hints."),
        ("TODO+ orphan cards", str(todo_plus_orphans), "0", "Spec-required runtime invariant."),
        ("BACKLOG/ICEBOX orphan ideas", str(cats["orphan_backlog_icebox"]), "allowed but reviewed", "Lightweight idea backlog remains possible."),
        ("active tasks", str(active), "<=1 per agent", "Resume ambiguity and WIP limit."),
        ("DONE history-chain completeness", f"{complete}/{total_done} ({ratio:.0%})", "trend up for new tasks", "Legacy debt is expected; process-era tasks should be complete."),
        ("research routing warnings", str(cats["research_routing"]), "0 live", "Research-like live tasks should route to researcher."),
        ("DONE overflow boards", str(cats["done_overflow"]), "0", "Archive when DONE > threshold."),
        ("boards", str(board_count), "informational", "Active board files scanned."),
        ("cards", str(len(board_map)), "informational", "Active + archived card slugs."),
        ("specs", str(len(specs)), "informational", "Spec files scanned."),
    ]
    return rows


def render(tasks: Path, *, board: str | None = None, project: str | None = None) -> str:
    tasks = lb.resolve_tasks_dir(tasks)
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    _board_names, _projects, label = resolve_scope(tasks, board=board, project=project)
    rows = metric_rows(tasks, board=board, project=project)
    lines = [
        f"# Autonomous Loop Metrics Snapshot — {now}",
        "",
        f"Scope: {label}",
        "",
        "| KPI | Current | Target | Interpretation |",
        "|---|---:|---|---|",
    ]
    for metric, current, target, note in rows:
        lines.append(f"| {metric} | {current} | {target} | {note} |")
    lines.extend([
        "",
        "## Baseline Use",
        "",
        "Use this output as the current baseline before a workflow change. After the change, run the same command and compare `Current` values against targets.",
    ])
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="Print read-only autonomous loop KPI snapshot.")
    ap.add_argument("workspace", help="Workspace root or tasks/ directory")
    ap.add_argument("--board", help="Limit metrics to one board file, e.g. claude-obsidian-kanban.md")
    ap.add_argument("--project", help="Limit metrics to one project/board stem, e.g. claude-obsidian-kanban")
    args = ap.parse_args()
    tasks = lb.resolve_tasks_dir(Path(args.workspace).expanduser())
    if not tasks.is_dir():
        print(f"✗ tasks/ folder not found: {tasks}", file=sys.stderr)
        return 2
    try:
        print(render(tasks, board=args.board, project=args.project))
    except ScopeError as exc:
        print(f"✗ {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
