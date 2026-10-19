"""Evidence gate for opt-in dynamic workflows. Standard-library only.

The journal is supplementary; Kanban board/spec remain the task lifecycle.
A dynamic task cannot enter DONE without a successful run and independent checks.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

SLUG_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")


def journal_path(tasks: Path, slug: str) -> Path:
    if not SLUG_RE.fullmatch(slug) or slug in (".", ".."):
        raise ValueError("invalid task slug")
    return tasks / ".dynamic-workflows" / "runs" / f"{slug}.json"


def save_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".run-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def artifact_digest(workspace: Path, name: str) -> str:
    """Only ordinary files within the workspace are eligible as evidence."""
    p = workspace / name
    if p.is_symlink() or not p.is_file() or not p.resolve().is_relative_to(workspace.resolve()):
        raise ValueError(f"artifact absent or outside workspace: {name}")
    return hashlib.sha256(p.read_bytes()).hexdigest()


def done_gate(tasks: Path, slug: str) -> tuple[bool, str]:
    path = journal_path(tasks, slug)
    if not path.is_file():
        return False, f"dynamic workflow evidence missing: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != 1 or data.get("task") != slug:
            return False, "journal identity/version mismatch"
        run = data.get("run", {})
        if run.get("status") != "completed" or run.get("exit_code") != 0:
            return False, "workflow has not completed successfully"
        if run.get("approved") is not True:
            return False, "workflow has no explicit approved:true"
        workflow_name = run.get("workflow")
        workflow_sha = run.get("workflow_sha256")
        if not isinstance(workflow_name, str) or not isinstance(workflow_sha, str):
            return False, "workflow code fingerprint missing"
        if artifact_digest(tasks.parent, workflow_name) != workflow_sha:
            return False, "workflow script changed since execution"
        inputs_name = run.get("inputs")
        inputs_sha = run.get("inputs_sha256")
        if inputs_name is not None:
            if not isinstance(inputs_name, str) or not isinstance(inputs_sha, str):
                return False, "workflow input fingerprint missing"
            if artifact_digest(tasks.parent, inputs_name) != inputs_sha:
                return False, "workflow inputs changed since execution"
        check = data.get("verification", {})
        if not check.get("passed") or check.get("exit_code") != 0 or not check.get("command"):
            return False, "independent verification missing or failed"
        artifacts = check.get("artifacts")
        if not isinstance(artifacts, dict) or not artifacts:
            return False, "no verified artifacts"
        workspace = tasks.parent
        for name, digest in artifacts.items():
            if not isinstance(name, str) or not isinstance(digest, str):
                return False, "malformed artifact evidence"
            if artifact_digest(workspace, name) != digest:
                return False, f"artifact changed since verification: {name}"
    except (OSError, ValueError, TypeError, AttributeError, json.JSONDecodeError) as exc:
        return False, f"invalid dynamic workflow evidence: {exc}"
    return True, "successful run, independent verification and artifact hashes match"
