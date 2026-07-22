---
name: "memory-wiki-router"
description: "Route incoming knowledge into the right memory wiki layer, page type, and safety flow."
---

# Memory Wiki Router

Use this skill when the user asks to remember, structure, sort, classify, archive, analyze, or preserve incoming knowledge in memory wiki; when a request includes decisions, questions, rules, people, projects, systems, sources, or automation ideas; or when the user says the wiki brain should auto-sort knowledge.

## Goal

Make memory wiki behave like an automatically sorted second brain. Every incoming knowledge item should be classified, routed, written or queued, linked to sources, and checked for open questions.

## Core route

```text
intake → classify → search existing pages → route → write/update → link/evidence → lint/review
```

## Knowledge layers

- `MEMORY.md`: durable user preferences, absolute rules, long-term behavioral constraints, safety policies, and core facts about the user.
- Daily memory notes: raw day log, temporary context, episodic notes.
- Memory wiki: structured knowledge: entities, concepts, sources, syntheses, reports, open questions.
- Task system: executable tasks, backlog, DoD, status, decomposition.
- `TOOLS.md`: environment-specific operational notes and tool quirks.
- `inbox.md`: uncertain or low-confidence items awaiting review.

## Wiki page groups

- `sources/`: raw materials, imported documents, emails, chats, transcripts, web pages.
- `entities/`: people, projects, systems, organizations, products, durable objects.
- `concepts/`: ideas, decisions, rules, policies, automations, patterns.
- `syntheses/`: compiled summaries, maps, reviews, rollups.
- `reports/`: generated dashboards, open questions, health reports.
- `inbox.md`: unclear items.

## Classification table

| Incoming item | Primary type | Target |
|---|---|---|
| User says “remember this rule” | rule | `MEMORY.md` + `concepts/rules` |
| Rationale for a choice | decision | `concepts/decisions` |
| Person/context relationship | person | `entities/people` |
| Project fact | project | `entities/projects` |
| Tool/system/config fact | system | `entities/systems` or `TOOLS.md` |
| Automation idea | automation/idea | `concepts/automations` or `concepts/ideas` |
| Explicit or implicit unanswered question | question | `reports/open-questions.md` + related page |
| Analysis/summary | synthesis | `syntheses` |
| Raw document/message/source | source | `sources` |
| Actionable request | task | task system, with wiki link if useful |
| Unclear item | unknown | `inbox.md` |

## Routing algorithm

1. Determine whether the user request is an action, knowledge capture, or both.
2. Classify the primary type: `person`, `project`, `system`, `decision`, `rule`, `idea`, `question`, `synthesis`, `source`, `task`, `automation`, or `unknown`.
3. Identify domain: `openclaw`, `finance`, `people`, `work`, `health`, `automation`, `learning`, `household`, `travel`, or `unknown`.
4. Run `wiki_search` before creating new wiki pages.
5. If a close page exists, update or create a synthesis linked to it; avoid duplicates.
6. Use `wiki_apply` for syntheses and metadata when possible.
7. Include source ids, claims, evidence, confidence, contradictions, and questions.
8. Route low-confidence items to `inbox.md` or ask the user.
9. After meaningful wiki updates, run `wiki_lint`.
10. Never perform external actions or destructive changes unless the user explicitly confirms or a durable rule already allows it.

## Confidence policy

| Confidence | Action |
|---|---|
| `>= 0.85` | Write to target page. |
| `0.60–0.84` | Write to target page and add an open question. |
| `0.40–0.59` | Route to `inbox.md` and propose classification. |
| `< 0.40` | Ask the user. |

## Intake card

Normalize incoming knowledge mentally or in notes as:

```yaml
intake:
  raw: ""
  sourceKind: chat-message | email | file | image | audio | web | calendar | manual
  capturedAt: YYYY-MM-DDTHH:mm:ss+03:00
classification:
  primaryType: person | project | system | decision | rule | idea | question | synthesis | source | task | automation | unknown
  domain: openclaw | finance | people | work | health | automation | learning | household | travel | unknown
  confidence: 0.0
routing:
  targetLayer: MEMORY.md | daily-memory | wiki | tasks | tools | inbox
  targetFolder: entities | concepts | syntheses | sources | reports | inbox
  targetPage: ""
links:
  relatedPages: []
claims:
  - id: ""
    text: ""
    status: supported | synthesis | tentative | contradicted
    confidence: 0.0
safety:
  externalAction: false
  confirmationRequired: false
nextAction: ""
```

## Templates

### Entity

```yaml
pageType: entity
entityType: person | project | system | organization | product
canonicalId: ""
aliases: []
privacyTier: local-private
bestUsedFor: []
notEnoughFor: []
lastRefreshedAt: YYYY-MM-DD
relationships: []
claims: []
```

### Decision

```yaml
pageType: concept
conceptType: decision
decisionDate: YYYY-MM-DD
status: active | superseded | draft
context: ""
options: []
chosenOption: ""
rationale: ""
consequences: []
revisitAt: null
claims: []
```

### Automation

```yaml
pageType: concept
conceptType: automation
status: idea | planned | active | paused | deprecated
trigger: ""
conditions: []
actions: []
memory: []
notify: []
safety:
  externalAction: false
  confirmationRequired: true
state: ""
owner: "<user>"
claims: []
```

## Anti-patterns

- Do not put everything in `syntheses/`.
- Do not create duplicate pages when an existing entity/concept is close enough.
- Do not use `MEMORY.md` as a dumping ground.
- Do not mark proposed external actions as completed.
- Do not hide open questions in prose; list them explicitly.
- Do not overwrite human note blocks.

## Example user-specific priorities

1. OpenClaw/system knowledge.
2. Task/project management.
3. Automation ideas and monitors.
4. People/CRM.
5. Finance, habits, and routines.
6. Decision log.

## Evidence and safety

Every durable claim should include evidence when the tool supports it. Prefer `chat-message`, `file`, `web`, `document`, `memory`, or `analysis` evidence kinds.

External or destructive actions require explicit confirmation unless a durable user-approved rule says otherwise.
