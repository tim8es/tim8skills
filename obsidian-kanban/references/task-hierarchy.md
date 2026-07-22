# Task Hierarchy — obsidian-kanban

```
Epic   🗃️  — direction / large feature, 2–8 weeks.   → always specs/<epic>.md
  └─ Task   📋  — specific work, 1–5 days         → always specs/<task>.md (minimum DoD + history); detailed decomposition if ≥3 subtasks / ≥2 dependencies
       └─ Subtask ✅ — atomic action, < 1 day    → a line inside the Task; its own file if > 10 lines of description
```

## Decomposition Rules

- **Every card must have a wikilink to a spec and must go through the analyst.** Plain-text cards without a wikilink are forbidden — even for a simple task, a minimal spec (DoD + history) is created. Add the card via the `add_card.py` script, not manually.
- Empty or unused wikilinks on the board are forbidden (a wikilink must resolve to an existing spec).
- Propose decomposing an epic into 3–7 tasks; wait for approval before creating files.
- After decomposition is approved, the epic's `## Tasks` must contain wikilinks to real child specs (`[[child-slug|Title]]`), created via `kanban.py new-task ... --epic <epic-slug> --card`. Plain-text items in `## Tasks` are only a draft: the linter issues a WARN in BACKLOG/ICEBOX and an ERROR in TODO+.
