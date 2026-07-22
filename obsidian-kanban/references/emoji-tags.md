# Emoji Tags — obsidian-kanban

Order on the tag line: `➕` → `🛫` → `📅` → `⏳` → priority → `🔁` → `✅`.

| Tag  | Meaning              | Format                                                                      |
| ---- | -------------------- | --------------------------------------------------------------------------- |
| `➕` | Creation date        | `➕ YYYY-MM-DD`                                                             |
| `🛫` | Start date           | `🛫 YYYY-MM-DD` — set explicitly by the analyst (`tags --start today`) when taking a BACKLOG idea into work; not a consequence of a transition |
| `📅` | Deadline              | `📅 YYYY-MM-DD`                                                             |
| `⏳` | Duration estimate    | `⏳ Nh` or `⏳ Nd` — **not a date**                                          |
| `🟥` | High priority        | —                                                                           |
| `🟨` | Medium priority      | —                                                                           |
| `🟩` | Low priority         | —                                                                           |
| `🔁` | Recurring task       | —                                                                           |
| `✅` | Completion date      | `✅ YYYY-MM-DD HH:MM` — set automatically by `move_card.py` when moved to DONE |
