"""kanban_utils.py — thin re-export facade (backward-compat).

Direct imports are preferred: board_io, workflow, spec_mutations.
This file guarantees existing code using `import kanban_utils as ku` keeps working.
"""
import lint_board as lb

from board_io import (  # noqa: F401
    SETTINGS_DEFAULT,
    MutationError,
    detect_script_prefix,
    parse_tag_line,
    build_tag_line,
    parse_board,
    emit_board,
    done_sort_key,
    find_boards,
    board_column_counts,
    resolve_single_board,
    resolve_board_for_slug,
    board_lock,
    mutate_board,
    _fsync_write,
)

from workflow import (  # noqa: F401
    compact_text,
    normalize_column,
    role_for_column,
    role_checklist,
    find_next_task,
    format_next_task,
)

from spec_mutations import (  # noqa: F401
    now_stamp,
    hist_stamp,
    mutate_spec,
    build_spec_text,
    scaffold_spec,
)

# Constants originally aliased from lint_board — kept here for backward compat
COLUMN_ORDER = lb.COLUMN_ORDER
COLUMN_TO_TIMESTAMP = lb.COLUMN_TO_TIMESTAMP
WIKILINK_RE = lb.WIKILINK_RE
