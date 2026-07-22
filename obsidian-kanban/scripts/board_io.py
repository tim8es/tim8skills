"""board_io.py — board I/O: parsing, serialization, tag lines, resolution, lock, mutations.

Exported by kanban_utils.py (backward-compat facade).
"""
from __future__ import annotations

import contextlib
import os
import re
import sys
import time
import uuid
from pathlib import Path

import lint_board as lb

COLUMN_ORDER = lb.COLUMN_ORDER
COLUMN_TO_STATUS = lb.COLUMN_TO_STATUS
WIKILINK_RE = lb.WIKILINK_RE

# list-collapse must have exactly one value per board column — generated from
# COLUMN_ORDER so a new column can never desync the default settings block.
SETTINGS_DEFAULT = (
    '%% kanban:settings\n'
    '{"kanban-plugin":"board","list-collapse":'
    '[' + ",".join(["false"] * len(COLUMN_ORDER)) + ']}\n%%'
)

_DONE_DATE_RE = re.compile(r"✅\s*(\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?)")

LOCK_STALE_SECS = 30  # a lock older than N seconds is considered stale

_DATE_PAT = r"\d{4}-\d{2}-\d{2}"


class MutationError(Exception):
    """Domain-level mutation error (missing section/field, index out of range …).
    message is printed by the caller to stderr; rc is the script's exit code."""

    def __init__(self, message: str, rc: int = 1):
        super().__init__(message)
        self.rc = rc


def detect_script_prefix(workspace: Path) -> str:
    """Computes SCRIPT_PREFIX (relative path from workspace to scripts/).
    Falls back to the canonical path only if scripts/ is outside the workspace."""
    scripts = Path(__file__).resolve().parent
    try:
        rel = scripts.relative_to(workspace.resolve())
        return str(rel).replace("\\", "/") + "/"
    except ValueError:
        return "obsidian-kanban/scripts/"


def parse_tag_line(line: str) -> dict:
    """Tags line (with a leading tab) -> components. Tolerant of missing tags."""
    t: dict = {}
    m = re.search(r"➕\s*(" + _DATE_PAT + ")", line)
    if m:
        t["created"] = m.group(1)
    m = re.search(r"🛫\s*(" + _DATE_PAT + ")", line)
    if m:
        t["start"] = m.group(1)
    m = re.search(r"📅\s*(" + _DATE_PAT + ")", line)
    if m:
        t["due"] = m.group(1)
    m = re.search(r"⏳\s*(\S+)", line)
    if m:
        t["estimate"] = m.group(1)
    if "🟥" in line:
        t["priority"] = "high"
    elif "🟨" in line:
        t["priority"] = "medium"
    elif "🟩" in line:
        t["priority"] = "low"
    if "🔁" in line:
        t["recurring"] = True
    m = re.search(r"✅\s*(" + _DATE_PAT + r"(?:\s+\d{2}:\d{2})?)", line)
    if m:
        t["done"] = m.group(1)
    return t


def build_tag_line(t: dict) -> str:
    """Components -> tags line with a leading tab in canonical order §7."""
    parts: list[str] = []
    if t.get("created"):
        parts.append(f"➕ {t['created']}")
    if t.get("start"):
        parts.append(f"🛫 {t['start']}")
    if t.get("due"):
        parts.append(f"📅 {t['due']}")
    if t.get("estimate"):
        parts.append(f"⏳ {t['estimate']}")
    if t.get("priority") == "high":
        parts.append("🟥")
    elif t.get("priority") == "medium":
        parts.append("🟨")
    elif t.get("priority") == "low":
        parts.append("🟩")
    if t.get("recurring"):
        parts.append("🔁")
    if t.get("done"):
        parts.append(f"✅ {t['done']}")
    return "\t" + " ".join(parts) if parts else ""


def parse_board(text: str):
    """Board -> (cols: {column: [card-blocks...]}, settings: str).
    A card block is a list of lines (the `- [ ]` line + its tags line), separated by blank lines."""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    m = re.search(r"\n(%%\s*kanban:settings.*?%%)\s*$", text, re.S)
    settings = m.group(1) if m else SETTINGS_DEFAULT
    body = text[:m.start()] if m else text

    cols: dict[str, list[list[str]]] = {c: [] for c in COLUMN_ORDER}
    cur = None
    buf: list[str] = []

    def flush(col):
        block: list[str] = []
        for ln in buf:
            if ln.strip() == "":
                if block:
                    cols[col].append(block)
                    block = []
            else:
                block.append(ln)
        if block:
            cols[col].append(block)

    for ln in body.split("\n"):
        hm = re.match(r"^##\s+(.+?)\s*$", ln)
        if hm and hm.group(1).strip() in COLUMN_TO_STATUS:
            if cur is not None:
                flush(cur)
            cur = hm.group(1).strip()
            buf = []
            continue
        if cur is not None:
            buf.append(ln)
    if cur is not None:
        flush(cur)
    return cols, settings


def emit_board(cols, settings) -> str:
    """Canonical serialization (§6): frontmatter, columns (heading + blank + blocks
    separated by blank lines), two blank lines before the settings block."""
    out = ["---", "", "kanban-plugin: board", "", "---", ""]
    for c in COLUMN_ORDER:
        out.append(f"## {c}")
        out.append("")
        for block in cols[c]:
            out.extend(block)
            out.append("")
    out.append("")  # second blank line before settings
    out.append(settings)
    return "\n".join(out) + "\n"


def resolve_board(boards: list, hint: str):
    """Finds a board by hint: exact name → stem (without .md) → prefix."""
    query = hint if hint.endswith(".md") else hint + ".md"
    exact = [b for b in boards if b.name == query or b.name == hint]
    if exact:
        return exact[0] if len(exact) == 1 else None
    stem = [b for b in boards if b.stem == hint]
    if stem:
        return stem[0] if len(stem) == 1 else None
    prefix = [b for b in boards if b.name.startswith(hint)]
    return prefix[0] if len(prefix) == 1 else None


def done_sort_key(block) -> str:
    """Sort key for a DONE card by the ✅ YYYY-MM-DD date."""
    for ln in block:
        m = _DONE_DATE_RE.search(ln)
        if m:
            return m.group(1)
    return ""


def find_boards(tasks: Path) -> list:
    """All board files in tasks/ (containing `kanban-plugin: board`), excluding SKILL.md and *-archive.md."""
    out = []
    for md in sorted(tasks.glob("*.md")):
        if md.name == "SKILL.md" or md.stem.endswith("-archive"):
            continue
        if "kanban-plugin: board" in md.read_text(encoding="utf-8", errors="replace"):
            out.append(md)
    return out


def board_column_counts(tasks_dir: Path) -> dict[str, dict[str, int]]:
    """Returns {board_slug: {column: count}} for all non-archive boards in tasks_dir."""
    result: dict[str, dict[str, int]] = {}
    for board in find_boards(tasks_dir):
        text = board.read_text(encoding="utf-8", errors="replace")
        cols, _ = parse_board(text)
        counts = {col: len(cards) for col, cards in cols.items() if cards}
        if counts:
            result[board.stem] = counts
    return result


def resolve_single_board(tasks: Path, board_hint=None):
    """Selects the single board for the operation. Returns (board: Path|None, err: str|None)."""
    boards = find_boards(tasks)
    if not boards:
        return None, f"✗ No board files in {tasks} (kanban-plugin: board)."
    if board_hint:
        resolved = resolve_board(boards, board_hint)
        if resolved is None:
            candidates = [b for b in boards
                          if b.name.startswith(board_hint) or b.stem == board_hint]
            if candidates:
                names = ", ".join(b.name for b in candidates)
                return None, f"✗ --board {board_hint!r} is ambiguous: {names}. Please specify the name."
            names = ", ".join(b.name for b in boards)
            return None, f"✗ Board {board_hint!r} not found in {tasks}. Available: {names}"
        return resolved, None
    if len(boards) > 1:
        names = ", ".join(b.name for b in boards)
        return None, f"✗ Several boards in tasks/ ({names}). Specify --board <name.md> or a prefix."
    return boards[0], None


def _slug_in_cols(cols: dict, slug: str) -> bool:
    """Whether a card with the given slug exists on the parsed board."""
    for blocks in cols.values():
        for block in blocks:
            if not block:
                continue
            m = WIKILINK_RE.search(block[0])
            if m and m.group(1).strip() == slug:
                return True
    return False


def resolve_board_for_slug(tasks: Path, slug: str, board_hint=None):
    """Selects the board for an operation on an EXISTING card <slug>. (Path|None, err|None)."""
    if board_hint:
        return resolve_single_board(tasks, board_hint)
    boards = find_boards(tasks)
    if not boards:
        return None, f"✗ No board files in {tasks} (kanban-plugin: board)."
    if len(boards) == 1:
        return boards[0], None
    matches = [b for b in boards
               if _slug_in_cols(parse_board(b.read_text(encoding="utf-8", errors="replace"))[0], slug)]
    if len(matches) == 1:
        return matches[0], None
    names = ", ".join(b.name for b in boards)
    if not matches:
        return None, (f"✗ Card [[{slug}]] not found on any board ({names}). "
                      f"Specify --board <name.md>.")
    return None, (f"✗ Card [[{slug}]] found on several boards ({names}). "
                  f"Specify --board <name.md>.")


def _pid_is_alive(pid: int) -> bool | None:
    """Best-effort cross-platform liveness check.

    Returns True/False when the check could be performed, or None when
    liveness could not be determined (caller must then treat the holder
    as alive — i.e. NOT steal the lock).
    """
    if pid <= 0:
        return None
    if os.name == "nt":
        try:
            import ctypes

            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            if not handle:
                return False
            ctypes.windll.kernel32.CloseHandle(handle)
            return True
        except Exception:
            return None
    else:
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            # Process exists but we can't signal it — treat as alive.
            return True
        except Exception:
            return None


@contextlib.contextmanager
def board_lock(tasks_dir, retries: int = 10, delay: float = 0.15):
    """Cross-platform file lock via atomic mkdir (O_EXCL semantics).

    The stamp file holds "pid:timestamp". Before forcibly reclaiming a
    stale lock, it checks whether the holder process is alive —
    if liveness could not be determined (cross-platform checking is
    unreliable), the lock is NOT stolen (conservative fallback: just wait).
    The reclaim itself is atomic — the stale directory is renamed to a unique
    temp name before removal, so competing processes can never
    both believe they successfully acquired the lock at the same time.
    """
    lock_dir = Path(tasks_dir) / ".kanban-lock"
    stamp = lock_dir / "stamp"
    acquired = False

    for _ in range(retries):
        try:
            lock_dir.mkdir(parents=False, exist_ok=False)
            stamp.write_text(f"{os.getpid()}:{time.time()}", encoding="utf-8")
            acquired = True
            break
        except FileExistsError:
            try:
                raw = stamp.read_text(encoding="utf-8").strip()
                if ":" in raw:
                    pid_str, ts_str = raw.split(":", 1)
                else:
                    # Backward-compat: the old stamp format held only a timestamp.
                    pid_str, ts_str = "0", raw
                held_pid = int(pid_str)
                age = time.time() - float(ts_str)
                if age > LOCK_STALE_SECS:
                    alive = _pid_is_alive(held_pid)
                    if alive:
                        # Holder is alive — don't steal, just keep waiting.
                        pass
                    elif alive is None:
                        # Liveness could not be determined — conservatively don't steal.
                        print(
                            f"⚠️  kanban-lock: stale lock ({age:.0f}s), but "
                            "holder liveness could not be determined — waiting instead of stealing",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            f"⚠️  kanban-lock: stale lock ({age:.0f}s > "
                            f"{LOCK_STALE_SECS}s), holder (pid={held_pid}) is dead"
                            " — forcibly reclaiming",
                            file=sys.stderr,
                        )
                        # Atomic reclaim: rename to a unique name before
                        # rmdir. If a competing process has already renamed/removed
                        # the directory, rename here raises OSError and we simply
                        # wait for the next attempt — no double "success".
                        stale_name = lock_dir.with_name(
                            f".kanban-lock.stale-{uuid.uuid4().hex}"
                        )
                        try:
                            os.rename(lock_dir, stale_name)
                        except OSError:
                            pass
                        else:
                            try:
                                (stale_name / "stamp").unlink()
                            except OSError:
                                pass
                            try:
                                stale_name.rmdir()
                            except OSError:
                                pass
                            continue
            except (OSError, ValueError):
                pass
            time.sleep(delay)

    if not acquired:
        print(
            f"❌ kanban-lock: failed to acquire after {retries} attempts"
            f" ({retries * delay:.1f}s). "
            "Retry the command or remove tasks/.kanban-lock/ manually.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        yield
    finally:
        try:
            stamp.unlink()
        except OSError:
            pass
        try:
            lock_dir.rmdir()
        except OSError:
            pass


def _fsync_write(path: Path, content: str, *, retries: int = 4) -> None:
    """Writes with flush+fsync — guards against Windows buffered-write not persisting to disk.

    Windows intermittently raises a transient ``OSError`` (e.g. ``[Errno 22] Invalid argument``)
    from ``open()``/write that clears on a second attempt, so the whole write is retried with a
    short backoff before the last error is re-raised. ``os.fsync`` is best-effort: it can fail
    with EINVAL on some Windows/network filesystems, and since the bytes are already flushed to
    the OS an fsync-only failure must not abort an otherwise-successful write.
    """
    for attempt in range(retries):
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(content)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except OSError:
                    pass  # fsync unsupported/transient on this fs; bytes already flushed
            return
        except OSError:
            if attempt == retries - 1:
                raise
            time.sleep(0.15 * (attempt + 1))


def mutate_board(tasks, board_file: Path, transform, *, dry_run: bool = False) -> tuple[int, str]:
    """Shared envelope for mutating the board file tasks/<board>.md."""
    lock = board_lock(tasks) if not dry_run else contextlib.nullcontext()
    with lock:
        cols, settings = parse_board(board_file.read_text(encoding="utf-8"))
        try:
            cols, inner = transform(cols, settings)
        except MutationError as e:
            return e.rc, str(e)
        if dry_run:
            return 0, f"[dry-run] {inner}"
        _fsync_write(board_file, emit_board(cols, settings))
    return 0, f"✅ {inner}"
