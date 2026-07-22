# agent-mind

A configuration system for focused AI agents based on a knowledge graph.

An agent doesn't "know everything" — it **acts in a specific way** in a specific
context, guided by directive instructions from the graph. The knowledge graph is not
an encyclopedia, but a set of patterns: "when I see X — I do Y — because Z."

---

## File structure

```
agent-mind/
├── README.md                          this documentation
├── build.py                           build tool (universal)
├── persona.md                ✏️ edited by hand — agent role
├── SKILL.md                  ⚙️ generated — persona + routing table
├── references/                        ADRs and design decisions
│   └── adr-001-learning-architecture.md
└── knowledge/
    ├── _digest.md            ⚙️ generated — digest of high-confidence directives
    ├── _edges.md             ⚙️ generated — cross-domain edge graph
    └── engineering/
        ├── _scope.md         ✏️ edited by hand — cluster context
        ├── naming.md         ✏️ edited by hand — directive knowledge
        ├── security.md       ✏️ edited by hand
        └── ...
```

**Rule:** files marked `⚙️` are never edited by hand — they get overwritten on every
run of `build.py`. All changes go into `✏️` files.

---

## Architectural principles

### 1. One skill = one focused agent

Each skill describes a specific role (`persona.md`), not a universal assistant.
The role removes ambiguity: `security` in the software-reviewer skill means
application security in code. In a safety-inspector skill, the same cluster would
mean occupational safety on the shop floor.

### 2. Flat routing table, no intermediate steps

`SKILL.md` contains the full table of all domains — the agent reads it once and
loads the needed file directly. Hierarchical indexes (an `_index.md` per cluster)
would require an extra read call at every level of the hierarchy — that's overhead
with no benefit.

```
Bad:  SKILL.md → _index.md → domain.md   (3 operations)
Good: SKILL.md → domain.md               (2 operations, routing table lives in SKILL.md)
```

Growing the number of domains only grows the size of the table in the already-loaded
`SKILL.md` — that's free. An extra file read costs latency and tokens.

### 3. _scope.md resolves naming collisions

Words like `security`, `naming`, `systems` are polysemous. `_scope.md` in each
cluster explicitly pins down what this cluster means **within this particular
skill** and what is excluded. This lets you have both `engineering/security` and
`safety/security` in different skills without confusion.

### 4. Directive knowledge format (Trigger → Directive → Because)

Knowledge is stored not as descriptions ("SQL injection is...") but as action
patterns:

```
Trigger:   the observable condition that activates the directive
Directive: what to do when the trigger fires
Because:   the root cause — what property it protects and by what mechanism
Smells:    observable violations (help recognize the trigger)
```

This keeps the agent focused: it doesn't reason in generalities, but applies a
specific pattern to a specific situation.

### 5. _digest.md — an orientation layer without reading the whole graph

The OpenClaw approach: a compiled digest of high-confidence directives from all
domains. The agent loads it when unsure which domain to pick — getting an overview
in one read instead of reading through all domain files one by one.

### 6. File hierarchy — for humans, not for routing

`knowledge/engineering/security.md` is a convenient path for both humans and the
agent to read. But navigation happens through the table in `SKILL.md`, not by
traversing directories. Folders are organization, not a lookup mechanism.

### 7. The graph grows on its own, but conservatively (self-learning)

The agent adds to the graph during work — following a strict process (the LEARN
workflow + the Self-learning protocol in `persona.md`). The key invariant: **a
polluted graph is worse than a small one**. So new knowledge enters at `low`
confidence in "quarantine" (it doesn't make it into `_digest.md`) and is only
promoted to `high` as corroboration accumulates. More detail in the
[Self-Learning](#self-learning) section below.

---

## Domain-file format

Every domain file starts with a YAML frontmatter, followed by claims:

```yaml
---
domain: security          # must match the file name without .md
cluster: engineering      # must match the folder name
summary: "..."            # one line ≤200 characters — appears in the routing table
updated: 2026-06-25
related:
  - domain: engineering/architecture    # full path cluster/domain
    type: supports                      # supports | enables | refines | tension
    edge: "one-line description of the relationship"
---
```

### Claim format

```markdown
## [eng.S2] Short principle title
**Confidence**: high | medium | low
**Severity**: critical | major | minor | style
**Context**: web-backend, database, api, ...
**Updated**: YYYY-MM-DD
**Evidence**: Source 1; Source 2
**Trigger**: The observable condition that activates this directive.
**Directive**: What to do when the trigger fires — a concrete action.
**Because**: The root cause — what property (readability / maintainability /
             security / performance / scalability) it protects and by what
             mechanism.
**Smells**: Observable signs that this directive is being violated.
**When not**: Conditions under which the directive doesn't apply. (optional)
**See also**: [id], [id]  (optional)
```

**Naming ID:** `[cluster-prefix.DomainAbbr + number]`
- `eng` = engineering
- `S` = security, `N` = naming, `F` = functions, `R` = readability, etc.
- Example: `[eng.S2]`, `[eng.N1]`, `[prod.PM3]`

**Confidence:**
- `high` — makes it into `_digest.md`, proven in practice, authoritative source
- `medium` — reasonably grounded, but context-dependent or contested
- `low` — a hypothesis, needs corroboration

**Severity** (only for `high` claims — controls the badge in `_digest.md`):
- `critical` / `major` — get a badge in the digest, priority during review
- `minor` / `style` — no badge; a missing `Severity` field is treated as `minor`

**Edge types:**
- `supports` — satisfying A makes it easier to satisfy B
- `enables` — B is only achievable once A is satisfied
- `refines` — A is a more specific version of B
- `tension` — A and B pull in different directions; when they meet, name the
  trade-off out loud

---

## How to add knowledge

### A new claim in an existing domain

1. Open the relevant `knowledge/<cluster>/<domain>.md`
2. Append the claim at the end of the file in the format above
3. Update `updated:` in the frontmatter
4. Running `build.py` is **not required** — the changes are picked up without a
   rebuild

### A new domain in an existing cluster

```bash
python build.py --add-domain "name" \
                --cluster engineering \
                --summary "one line describing what this domain covers"
```

Creates `knowledge/engineering/name.md` with a scaffold template.
Fill in the claims, then:

```bash
python build.py
```

### A new cluster (a new subject area)

```bash
python build.py --add-domain "risk-assessment" \
                --cluster safety \
                --summary "Occupational hazard identification and mitigation"
```

Automatically creates `knowledge/safety/_scope.md` — fill in:
- What this cluster means **within this particular skill**
- What is explicitly excluded (prevents collisions with same-named domains)

Then run `python build.py`.

### A new cross-domain edge

Add to the `related:` block of the source domain file:

```yaml
related:
  - domain: engineering/performance
    type: tension
    edge: "⚠ description of the trade-off between these domains"
```

Then run `python build.py` — `_edges.md` is rebuilt automatically.

**An edge is declared in exactly one file (unidirectional).** `build.py` deduplicates
edges by the unordered pair `{A, B}` and keeps only the entry from the file that
comes first alphabetically — the type and note from the second file are silently
discarded. So the A↔B relationship is described in exactly one domain file, not
both. `python build.py --validate` warns if a pair is declared in both files (a
type conflict or a redundant duplicate).

---

## Self-Learning

The graph is not a static encyclopedia but a **learning system**: the agent adds
to it during work. The operational source of truth is `persona.md` (the LEARN
workflow + the Self-learning protocol); it arrives in context via `SKILL.md`.
Here we document the architecture. The full architectural decision (the two
planes, the mapping onto tokens/memory/invocation, the phase roadmap, the
trade-offs around hooks) lives in
`references/adr-001-learning-architecture.md`.

### Why, and the main risk

The value is that findings from one session become directives for future ones.
The main risk is **graph pollution**: noise, duplicates, over-generalizations, and
project-specific facts degrade every subsequent task. That's why the process is
**conservative by default**: a high bar for writing + an explicit confidence
lifecycle.

### How the agent recognizes WHAT to capture (recognition)

The most fragile part of any learning system isn't "how to record it" but "how to
**notice** that a moment is learnable." If capture depends on whether the agent
happens to remember to do it, it doesn't work. That's why recognition is made
**active and deterministic**: a set of observable signals that the agent scans for
at the end of every WRITE / REVIEW / REFACTOR (and continuously, for Gap). This is
a checkpoint in the workflow, not a "reminder."

| Signal (what you observe) | What it means | Candidate action |
|---|---|---|
| **Gap** — reasoned from general knowledge because *no directive covered* the case (persona already requires saying this out loud) | the graph is incomplete | a new `low` claim / a new domain |
| **Repeat** — the same recommendation/fix in ≥2 different contexts | a real pattern (rule of three) | a new `low`/`medium` claim |
| **Miss** — reality (a bug, a test, a benchmark) contradicts what the directive predicted | the claim is wrong/too narrow | refine/demote the claim + Evidence |
| **Override** — the user or a test rejected the directive's recommendation | strong counter-evidence | refine the claim; possibly a `tension` edge |
| **Conflict** — two directives pulled in different directions, a balance had to be chosen | the relationship is missing/implicit | a new/refined `tension` edge |

**Gap is the anchor signal:** persona already forces the agent to declare "no
directive covers this" — every such declaration is a candidate for capture. The
signal only *suggests*; the capture gate decides. Extensibility: to teach the
agent a new **kind** of finding, add a row to the table.

### How it works: the lifecycle (state machine)

Every piece of knowledge goes through an explicit, inspectable state machine — not
a judgment call:

```
[signal fires]
   │  capture gate (5 criteria) ──fail──► discard (name the reason)
   ▼
dedup search in the domain + _digest ──hit──► strengthen the existing claim (+Evidence)
   ▼
CANDIDATE (low)      ← QUARANTINE: visible when the domain is loaded, NOT in
   │                    _digest.md, does NOT drive default behavior
   │  +independent Evidence
   ▼
CORROBORATED (medium)
   │  +independent Evidence, an authoritative source, no unresolved contradictions
   ▼
OPERATING (high)  →  _digest.md   ← always loaded, drives behavior
   │
   └─► review: stale/unconfirmed → RETIRED;  contradicts a stronger claim → demote / tension
```

- **Transitions are gated by Evidence**, not by desire: promotion only happens when
  new independent corroboration has been added (in the `Evidence:` field).
- **The quarantine boundary is a digest filter**: `build_digest()` only collects
  `high` claims. The mechanism already exists — no separate storage for candidates
  is needed.
- **The review queue is a query, not a file:** `python build.py --candidates`
  prints all `low`/`medium` claims with their age (from `Updated:`). This keeps
  the quarantine inspectable so it doesn't "rot" silently — DRY, no parallel
  storage.
- **Provenance** lives in the `Evidence:` field (date + root cause/source). There's
  no separate field (`Evidence` is reused — [eng.M3] YAGNI, [eng.M1] DRY).
- **Enforcement** — `python build.py --validate`: every claim has a `Because`,
  every `high` claim has `Evidence`, confidence is one of `high|medium|low`. The
  invariants are enforceable.
- **GC** — a periodic dogfooding audit retires stale `low` claims, resolves
  contradictions, merges duplicates (the signal comes from `--candidates`).

### Reliable capture: WAL → distillation (phase 2)

Capture depends on the model's discipline — unreliable. The solution is borrowed
from databases (**write-ahead log → compaction**): separate cheap, always-on
**observation** from expensive, periodic **distillation**.

- **Observation (WAL).** When a recognition signal fires, the agent appends one
  line to `knowledge/_journal.md` via the command
  `python build.py --log-signal <domain> --type Gap|Repeat|Miss|Override|Conflict --note "..."`.
  The journal is append-only, one line = `date | domain | type | summary`,
  recording is deterministic (a script, not a manual edit). This is cheap and
  requires no judgment — it just records that the moment was learnable. The graph
  itself **does not change**.
- **Distillation (compaction).** Periodically (not every task)
  `python build.py --distill [--since YYYY-MM-DD]` reads the journal, groups
  repeats (one trigger seen ≥2× — rule of three, [eng.M2]), and prints **proposed
  claim skeletons** at `low` confidence with provenance (dates + source) in
  `Evidence:`. Distillation only *proposes* — it **does not write** to the
  domains; every skeleton goes through the normal capture gate + confidence
  lifecycle (entering at `low`). `--since` cuts off already-processed dates — one
  signal doesn't spawn duplicate candidates.

Portable: the base version works without harness hooks (the agent appends to the
journal, the script collects). Automating observation (a Stop hook, auto
`--log-signal`) is provided by the optional phase 3 (L2) — not a required
dependency.

### Extension points (why the architecture is extensible)

Extension means **adding data, not rewriting logic**:

| Extension axis | How | What it touches |
|---|---|---|
| A new **kind** of finding | a row in the Recognition table (`persona.md`) | only protocol text |
| A new **subject area** | `build.py --add-domain … --cluster …` | auto-generated row in the routing table |
| A new **cluster** (a different skill) | `--add-domain` creates `_scope.md` | isolation from same-named domains |
| A new **confidence rule** | a threshold/step in the lifecycle | one protocol block |
| A new **invariant** | a check function in `check_claim_hygiene()` | one independent check |
| A new **queue view** | a command in the style of `--candidates` | one function + `iter_claims()` |

Everything rests on a single shared parser, `iter_claims()` (a single parsing
source for digest, validate, and candidates) — new tools read the graph the same
way, so they never drift apart.

### Rules and constraints (in brief)

Only write a claim if it is **generalizable, reusable, new, grounded (Because +
Evidence), and actionable** (Trigger → Directive). Do NOT write: project/user-
specific facts (→ task specs or session memory), one-off observations without a
root cause, style preferences without justification (that's a Nit, [eng.M9]),
restatements of existing claims, and "patterns" seen only 1-2 times ([eng.M2] rule
of three). Don't leave contradictions unaddressed silently — demote with a note, a
`tension` edge, or retire (don't delete without recording the reason). The full
checklist is in `persona.md`.

---

## build.py commands

```bash
python build.py                        # rebuild SKILL.md, _digest.md, _edges.md
python build.py --validate             # check frontmatter + claim hygiene + edges
python build.py --candidates           # review queue: low/medium claims (quarantine) with age
python build.py --log-signal DOMAIN    # append a recognition signal to _journal.md (WAL)
  --type TYPE                          # Gap|Repeat|Miss|Override|Conflict
  --note "..."                         # one-line summary
python build.py --distill              # propose claim skeletons from repeated journal entries
  --since YYYY-MM-DD                   # cut off already-processed dates (idempotency)
python build.py --add-domain NAME      # create a scaffold for a new domain
  --cluster CLUSTER                    # required
  --summary "..."                      # one-line description
python build.py --package [OUTDIR]     # package; uses skill-creator if present, otherwise a stdlib zip
```

**When to run build.py:**
- After `--add-domain` (a new domain → a new row in the routing table)
- After changing `summary:` in the frontmatter (updates the routing table)
- After changing `related:` (updates `_edges.md`)
- After changing `persona.md` (updates `SKILL.md`)
- **Not needed** after adding/changing claims within an existing domain

---

## Extending to other skills

This architecture is a universal template. For a new skill:

1. Copy the directory structure
2. Rewrite `persona.md`: the new agent role
3. Clear `knowledge/` of engineering domains
4. Add domains for the new subject area via `--add-domain`
5. Fill in each cluster's `_scope.md`
6. `python build.py --package`

Examples of applying the same architecture:
- `legal-reviewer` → knowledge/contracts/, knowledge/compliance/
- `safety-inspector` → knowledge/labor-safety/, knowledge/equipment/
- `data-analyst` → knowledge/statistics/, knowledge/visualization/
- `product-manager` → knowledge/strategy/, knowledge/metrics/

---

## Portability across Claude surfaces

The skill is portable across every Claude surface (Claude Code CLI, desktop,
claude.ai/code, IDE extensions, a skill shared with another Claude user):

- **Content is self-contained.** `persona.md`, `knowledge/`, `build.py` contain no
  absolute or environment-specific paths — `build.py` resolves everything from
  `Path(__file__).parent`. The only external dependency is `pyyaml`.
- **Packaging works everywhere.** `--package` looks for `skill-creator` via
  `$SKILL_CREATOR_PATH` and known Claude locations; if not found, it packages
  using stdlib `zipfile` (no external dependency). Ephemeral files (`_journal.md`,
  `__pycache__`) are excluded and gitignored — a shared skill is always clean.
- **Determinism — only the portable part is in the core.** The scripted control
  plane (`--validate`, `--claims`, `--candidates`, `--log-signal`, `--distill`)
  works in any Claude surface. Harness event hooks (settings.json: phase 3) are
  specific to the Claude Code CLI and are **not consistent** across all Claude
  surfaces — so they are **not part of the core**, and remain a local opt-in (see
  `references/adr-001-learning-architecture.md`).
