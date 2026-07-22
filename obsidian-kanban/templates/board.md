# Template: Project Kanban Board

Copy the content below into `tasks/<project-slug>.md`.
**Do not modify the frontmatter or the `%% kanban:settings %%` block.**

---

```
---

kanban-plugin: board

---

## BACKLOG



## ICEBOX



## TODO



## IN PROGRESS



## BLOCKED



## TESTING



## IN REVIEW



## UAT



## REJECTED



## REWORK



## DONE




%% kanban:settings
{"kanban-plugin":"board","list-collapse":[false,false,false,false,false,false,false,false,false,false,false]}
%%
```

---

## Example of a Filled Board

```
---

kanban-plugin: board

---

## BACKLOG

- [ ] [[auth-epic|DEV: Authentication System]]
	➕ 2026-05-18 🛫 2026-05-20 📅 2026-06-01 ⏳ 3d 🟥


## ICEBOX

- [ ] [[mobile-app|DEV: Mobile App]]
	➕ 2026-05-01 🛫 2026-07-01 ⏳ 14d 🟩


## TODO

- [ ] [[db-schema|DEV: Database Schema]]
	➕ 2026-05-15 🛫 2026-05-22 📅 2026-05-25 ⏳ 6h 🟨


## IN PROGRESS

- [ ] [[api-setup|DEV: API Server Setup]]
	➕ 2026-05-10 🛫 2026-05-18 📅 2026-05-23 ⏳ 8h 🟥


## BLOCKED

- [ ] [[oauth-integration|DEV: OAuth Integration]]
	➕ 2026-05-12 🛫 2026-05-19 📅 2026-05-27 ⏳ 4h 🟥


## TESTING

- [ ] [[jwt-service|DEV: JWT Service]]
	➕ 2026-05-08 🛫 2026-05-15 📅 2026-05-22 ⏳ 3h 🟥


## IN REVIEW

- [ ] [[ci-pipeline|OPS: CI/CD Pipeline]]
	➕ 2026-05-05 🛫 2026-05-12 📅 2026-05-20 ⏳ 4h 🟥


## UAT


## REJECTED

- [ ] [[auth-middleware|DEV: Auth Middleware]]
	➕ 2026-05-03 🛫 2026-05-10 📅 2026-05-18 ⏳ 2h 🟩


## REWORK


## DONE

- [x] [[project-setup|OPS: Project Initialization]]
	➕ 2026-05-01 🛫 2026-05-01 📅 2026-05-02 ⏳ 1h 🟨 ✅ 2026-05-02




%% kanban:settings
{"kanban-plugin":"board","list-collapse":[false,false,false,false,false,false,false,false,false,false,false]}
%%
```

---

## Format Rules (critical)

| Element | Rule |
|---------|---------|
| Frontmatter | Only `kanban-plugin: board`, no other fields |
| Card line | `- [ ] [[spec-slug\|TAG: Title]]` |
| Tags line | A separate line, starting with `\t` (tab) |
| Tag order | `➕` → `🛫` → `📅` → `⏳` → priority → `🔁` → `✅` (completion date, auto on DONE) |
| Empty columns | `## COLUMN` heading + one blank line |
| Card separator | A blank line between cards |
| Before `%%` | Two blank lines after the last card in DONE |
| Settings block | `list-collapse` has exactly 11 values (matching the number of columns); don't edit manually |
| Checkboxes | `- [ ]` open, `- [x]` closed (DONE only) |
