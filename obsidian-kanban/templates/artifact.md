# Template: Artifact

Copy into `tasks/artifacts/<artifact-slug>.md`.
`<artifact-slug>` must be unique relative to `tasks/specs/<task-slug>.md`:
wikilinks use the shortest path without folders, so `tasks/artifacts/foo.md`
must not exist at the same time as `tasks/specs/foo.md`.
An artifact is the **result** of work (lives permanently, read by people).
The spec references the artifact via a wikilink in `## Output / Artifacts`, and does not contain it.

---

```markdown
---
itemType: artifact
linkedTask: <task-slug>
status: draft
tags: [processes]
createdAt: YYYY-MM-DD HH:MM:SS
author: analyst
---

# Artifact Title

<!-- Artifact content. Structure is free-form — this is a deliverable, not a process spec. -->

## Sources
<!-- REQUIRED for research artifacts (lint_board.py checks this at the review gate).
     Each source is a separate list line with a link [text](url).
     Linter: no section → ERROR; source line without an http(s) URL → WARN. -->
- [Source name](https://example.com/...)
```

---

## YAML Fields — Reference

| Field | Allowed values | Required |
|------|---------------------|-------------|
| `itemType` | `artifact` | ✅ |
| `linkedTask` | `<task-slug>` — the task that created the artifact | ✅ |
| `status` | `draft` — draft; `actual` — final version | ✅ |
| `tags` | YAML array: `[research, concepts, tools, processes, retrospectives, summaries]` | ✅ — one or more |
| `createdAt` | `YYYY-MM-DD HH:MM:SS` | ✅ |
| `author` | the agent role that created the artifact | ✅ |

## Tags — Semantic Categories

| Tag | When to use |
|---|---|
| `research` | Results of research tasks, market analysis, competitor and technology analysis |
| `concepts` | Architectural decisions, design documents, proposals |
| `tools` | Scripts, utilities, configurations — description of how they work |
| `processes` | Workflows, protocols, process instructions |
| `retrospectives` | Analysis of past work, identified patterns, lessons learned |
| `summaries` | Summaries, reports, period/project wrap-ups |

## `## Sources` Section

Required for **research artifacts** (results of `RESEARCH:` tasks). `lint_board.py`
checks its presence and format at the review gate:

- the `## Sources` section is missing → **ERROR** (transition to `done` is blocked);
- a source line (starting with `-`) without an `http(s)://` URL → **WARN**.

Line format: `- [Source name/description](https://...)`. For non-research artifacts
(concepts, tools, processes), the section is optional but doesn't hurt.

---

## Filled Example

```markdown
---
itemType: artifact
linkedTask: research-epic-slug
status: actual
tags: [retrospectives, processes]
createdAt: 2026-06-01 17:00
author: analyst
---

# Dogfooding Analysis: Workflow Patterns

Results of the workflow run: observations, root causes, recommendations.
...
```
