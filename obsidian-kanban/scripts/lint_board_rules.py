# -*- coding: utf-8 -*-
"""Shared rule constants for lint_board.py.

Keep this module data-only: lint_board.py remains the CLI facade and owns the
checks/reporting flow, while rule tables and regex contracts live here.
"""

from __future__ import annotations

import datetime as dt
import re

# §5: board column -> canonical status
COLUMN_TO_STATUS = {
    "BACKLOG": "backlog",
    "ICEBOX": "icebox",
    "TODO": "ready",
    "IN PROGRESS": "in-progress",
    "BLOCKED": "blocked",
    "TESTING": "testing",
    "IN REVIEW": "review",
    "UAT": "uat",
    "REJECTED": "rejected",
    "REWORK": "rework",
    "DONE": "done",
}
# Column → spec transition-timestamp field. Sibling of COLUMN_TO_STATUS; stamped by
# move_card on first entry to the column (startedAt is set separately by the analyst).
COLUMN_TO_TIMESTAMP = {
    "TESTING": "testingAt",
    "IN REVIEW": "reviewAt",
    "DONE": "doneAt",
}
COLUMN_ORDER = list(COLUMN_TO_STATUS.keys())

VALID_STATUS = set(COLUMN_TO_STATUS.values())
# "unassigned" — a transitional value for cards created via the dashboard
# (the quick-create form doesn't decide task vs epic); the analyst assigns the
# real type when triaging BACKLOG. Valid ONLY in backlog/icebox — further along
# the flow the gate requires a concrete type.
VALID_ITEMTYPE = {"epic", "task", "subtask", "unassigned"}
ITEMTYPE_UNASSIGNED_OK_STATUS = {"backlog", "icebox"}
# §8: owner = agent role or user (11 agent roles + user).
# `uat` — the handoff-comment role in the UAT column.
VALID_OWNER = {
    "analyst", "planner", "developer", "researcher", "tester",
    "reviewer", "debugger", "documenter", "communicator", "archivist",
    "uat", "user",
}
VALID_PRIORITY = {"high", "medium", "low"}
REQUIRED_FIELDS = [
    "flowId", "itemType", "status", "parentId",
    "step", "owner", "priority", "createdAt", "updatedAt",
]

# §8: reminder — optional field; formats:
# YYYY-MM-DD | weekly:DOW | monthly:N | daily | null
REMINDER_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}"
    r"|weekly:(mon|tue|wed|thu|fri|sat|sun)"
    r"|monthly:([1-9]|[12]\d|3[01])"
    r"|daily|null)$"
)
FLOWID_RE = re.compile(r"^[^/]+/[^/]+/[^/]+$")  # §8: exactly 3 parts separated by /

STALE_DAYS = 3
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}(?::\d{2})?)?$")
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|(?:(?!\]\]).)*)?\]\]")
CARD_RE = re.compile(r"^\s*- \[[ xX]\] \[\[")
CARD_LINE_RE = re.compile(r"^\s*- \[[ xX]\]\s+\S")
TAG_SEQUENCE = ["➕", "🛫", "📅", "⏳", "✅"]
TODO_PLUS_COLUMNS = {"TODO", "IN PROGRESS", "BLOCKED", "TESTING", "IN REVIEW", "UAT", "REJECTED", "REWORK", "DONE"}
RESEARCH_TITLE_RE = re.compile(r"research|исслед|изуч|источник|source|video|видео|отчет|отч[её]т", re.IGNORECASE)
NON_RESEARCH_PREFIX_RE = re.compile(r"^(DEV|FIX|IMPROVE|TEST|DOC|OPS):", re.IGNORECASE)
DONE_CHAIN_BASE = ["BACKLOG → TODO", "TODO → IN PROGRESS", "IN PROGRESS → TESTING", "TESTING → IN REVIEW"]
DONE_CHAIN_FINALS = [["IN REVIEW → DONE"], ["IN REVIEW → UAT", "UAT → DONE"]]
PROCESS_GATE_START = dt.date(2026, 6, 28)
