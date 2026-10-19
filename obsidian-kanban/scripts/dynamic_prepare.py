"""Create a complete, reviewable Claude-style workflow from an existing Kanban spec.

The JS orchestration is copied from the native-compatible template, not rebuilt.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from dynamic_gate import journal_path
import board_io

ROLE_BLOCK = re.compile(r"^##\s+(Definition of Done \(DoD\)|Definition of Done|Test Checklist|Описание|Description)\s*$", re.I | re.M)
CHECK = re.compile(r"^\s*-\s*\[[ xX]\]\s*(.+)$", re.M)


def extract_task_spec(text: str, slug: str) -> dict:
    title = re.search(r"^#\s+(.+)$", text, re.M)
    heading = title.group(1).strip() if title else slug
    sections = {}
    for m in ROLE_BLOCK.finditer(text):
        nxt = text.find("\n## ", m.end())
        block = text[m.end():nxt if nxt >= 0 else len(text)]
        sections[m.group(1)] = block.strip()
    acceptance = []
    for key, block in sections.items():
        if "done" in key.lower():
            acceptance.extend(x.strip() for x in CHECK.findall(block) if x.strip())
    if not acceptance:
        raise ValueError("Spec has no concrete Definition of Done checklist. Complete the analyst role first.")
    task = heading + "\n\n" + "\n\n".join(
        f"{key}:\n{value}" for key, value in sections.items() if value
    )
    return {"task": task, "acceptance": acceptance}


def paths(workspace: Path, slug: str) -> tuple[Path, Path]:
    root = journal_path(workspace / "tasks", slug).parent.parent
    return root / "scripts" / (slug + ".workflow.js"), root / "inputs" / (slug + ".json")


def init(workspace: Path, slug: str, *, overwrite: bool = False) -> dict:
    spec = workspace / "tasks" / "specs" / (slug + ".md")
    if not spec.is_file() or spec.is_symlink():
        raise ValueError(f"Existing Kanban spec required: {spec}")
    source = spec.read_text(encoding="utf-8")
    task_input = extract_task_spec(source, slug)
    workflow, input_path = paths(workspace, slug)
    template = Path(__file__).resolve().parent.parent / "templates" / "dynamic-implementation.workflow.js"
    if not template.is_file():
        raise ValueError("Bundled upstream-compatible workflow template is missing")
    if workflow.is_symlink() or input_path.is_symlink():
        raise ValueError("Refusing to overwrite symbolic links")
    if (workflow.exists() or input_path.exists()) and not overwrite:
        # No silent overwrite of reviewed user scripts or saved input.
        return {"status":"already-initialized", "workflow":str(workflow.relative_to(workspace)),
                "inputs":str(input_path.relative_to(workspace)),
                "note":"Use --overwrite only after reviewing the existing script and inputs"}
    workflow.parent.mkdir(parents=True, exist_ok=True)
    input_path.parent.mkdir(parents=True, exist_ok=True)
    # Crash-safe per-file replacement. Authoring does not launch agents.
    _atomic_copy(template, workflow)
    _atomic_json(input_path, task_input)
    with board_io.board_lock(workspace / "tasks"):
        current = spec.read_text(encoding="utf-8")
        if re.search(r"^workflowMode:\s*dynamic\s*$", current, re.M) is None:
            if not current.startswith("---\n") or "\n---\n" not in current[4:]:
                raise ValueError("Spec has no valid YAML frontmatter")
            if re.search(r"^workflowMode:", current, re.M):
                current = re.sub(r"^workflowMode:.*$", "workflowMode: dynamic", current, count=1, flags=re.M)
            else:
                current = current.replace("---\n", "---\nworkflowMode: dynamic\n", 1)
            board_io._fsync_write(spec, current)
    return {"status":"initialized", "workflow":str(workflow.relative_to(workspace)),
            "inputs":str(input_path.relative_to(workspace)),
            "note":"Review the generated JS and args, then use plan and approved run"}


def _atomic_copy(src: Path, dst: Path):
    _atomic_bytes(src.read_bytes(), dst)


def _atomic_json(dst: Path, obj: dict):
    _atomic_bytes((json.dumps(obj, ensure_ascii=False, indent=2) + "\n").encode(), dst)


def _atomic_bytes(data: bytes, dst: Path):
    tmp = dst.with_name(dst.name + ".pending-" + str(os.getpid()))
    try:
        with open(tmp, "xb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, dst)
    finally:
        tmp.unlink(missing_ok=True)


def doctor(runner: Path | None) -> dict:
    result = {"python": sys.version.split()[0], "node": None, "codex": None,
              "runner": None, "ready_for_plan": False, "ready_for_run": False}
    for name in ("node", "codex"):
        try:
            p = subprocess.run([name, "--version"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, timeout=8)
            if p.returncode == 0:
                result[name] = p.stdout.strip()[:200]
        except (OSError, subprocess.TimeoutExpired):
            pass
    if runner and runner.is_file() and runner.name == "run-workflow.js":
        result["runner"] = str(runner)
    result["ready_for_plan"] = bool(result["runner"] and result["node"])
    result["ready_for_run"] = bool(result["ready_for_plan"] and result["codex"])
    return result
