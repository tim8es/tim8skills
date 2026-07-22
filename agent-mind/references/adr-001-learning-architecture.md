# ADR-001: Self-learning and efficiency architecture of agent-mind

**Status:** accepted (phases 1-2 implemented, phase 3 proposed) — 2026-07-03
**Task context:** `agent-mind-self-learning-protocol`, `agent-mind-learning-recognition-layer`,
`agent-mind-learning-wal-distill` (DONE)

## Context

The agent-mind skill is a learning graph of engineering directives. A question
arose: right now everything works **only through the agent's understanding**
(persona → SKILL.md), with no deterministic mechanisms. We need the most
efficient possible architecture along four axes: **(1) token** cost of the
workflow, **(2) memory** (reliable capture of knowledge), **(3) when to invoke
knowledge**, **(4) when the skill itself gets invoked**.

An honest assessment of the current state (2026-07-03): there are no deterministic
harness event hooks (settings.json: `UserPromptSubmit`, `PreToolUse`, `Stop`, ...)
in the repository. The "hooks" in the neighboring obsidian-kanban are internal
Python functions (`hooks.py`) that call *skill scripts*; they're deterministic
**provided** the agent has run the command. That is, even there, the decision to
"invoke" remains up to the agent.

## Decision: two planes (reasoning plane + control plane)

The key principle is to **separate probabilistic judgment from deterministic
execution** (analogous to control plane / data plane, CQRS). You can't force the
model to "think" or "remember" deterministically, but you can deterministically
**route, retrieve, capture raw material, and validate** — leaving only judgment to
the agent.

```
REASONING PLANE (probabilistic, prompt-based — portable to any harness)
  directives (claims) · recognition signals · capture gate · confidence decisions
        ▲ judgment                                    │ invokes
        │                                             ▼
CONTROL PLANE (deterministic)
  Level 1 — encapsulated in scripts (portable, agent runs the command):
     build.py: --validate (enforcement) · --claims (retrieval) · --candidates (queue)
  Level 2 — harness event hooks (Claude-Code-specific, requires opt-in in settings.json):
     UserPromptSubmit (trigger+injection) · PreToolUse (JIT knowledge) · Stop (capture WAL)
```

Properties: **dependency inversion** (the skill defines the contract, the harness
optionally provides a deterministic implementation), **graceful degradation**
(Level 1 works everywhere; Level 2 speeds things up where the harness supports
it), **core portability** is preserved (the README promises a universal
template — Level 2 must not become a hard dependency).

## Mapping onto the four efficiency axes

| Axis | Mechanism | Plane / status |
|---|---|---|
| **Tokens** | Progressive disclosure: SKILL(index) → `_digest`(compact) → domain(detail) on demand | reasoning · exists |
| | **Retrieval, not file loading**: `--claims <domain> --id ... --full` returns a slice, not the whole file; cost is proportional to relevance, not domain size | control L1 · **implemented** |
| | **Budget ∝ severity×confidence**: `critical`/`major` `high` claims — load eagerly (cheap, valuable); `minor`/candidates — only on demand. Reuses existing digest badges | reasoning/control · partial (badges exist; prioritization is a convention) |
| **Memory** | Confidence lifecycle + quarantine (only `high` → `_digest.md`) + `--candidates` as a query-based queue | exists |
| | **WAL → compaction**: the agent appends session signals to a journal via `--log-signal` (cheap, always-on); periodic `--distill` turns the journal into claim candidates. Separates observation from distillation. A Stop hook for auto-`--log-signal` is an optional accelerator (L2, phase 3) | control L1 · **implemented (phase 2)** |
| **When to invoke knowledge** | routing table + recognition signals; `--claims` makes invocation a cheap, targeted query | reasoning + control L1 · exists |
| | **JIT injection**: PreToolUse on Edit/Write with a SQL string → surface S1/S2 at the moment of action, not on prompt | control L2 · proposed (phase 3) |
| **When the skill gets invoked** | `description` frontmatter → the model decides (probabilistically) | reasoning · exists |
| | **Deterministic trigger**: UserPromptSubmit classifies intent (code keywords, presence of a diff, code paths) → activates the skill/injects the digest | control L2 · proposed (phase 3) |

## What was borrowed and what is new

**Best practices (borrowed):** progressive disclosure (Anthropic's skills guide),
control/data-plane separation (CQRS), RAG-like retrieval (local and
deterministic), WAL→compaction (databases), dependency inversion + graceful
degradation (SOLID), just-in-time context.

**New (synthesis on top of the graph's own metadata):**
- **A retrieval budget weighted by severity×confidence** — digest badges become a
  retrieval-priority signal, not just a review marker.
- **A review queue as a query, not a store** (`--candidates` on top of the
  confidence field; the digest=high filter already gives behavioral quarantine —
  no parallel storage needed).
- **Recognition signals tied to existing behavior** — the Gap signal reuses the
  already-mandatory "say it out loud if a directive doesn't cover the case."
- **A single shared parser `iter_claims()`** — digest, validate, candidates, and
  claims all read the graph the same way and never drift apart ([eng.M1] DRY).

## Roadmap (phases)

- **Phase 1 (implemented):** enforcement (`--validate` hygiene), retrieval
  (`--claims`), queue (`--candidates`), recognition layer in persona, shared
  `iter_claims()`, UTF-8 stdout. Portable, no harness coupling.
- **Phase 2 (implemented):** the session WAL journal `knowledge/_journal.md` +
  `build.py --log-signal` (observation, append-only) + `build.py --distill`
  (distillation of repeats into claim skeletons at `low` with provenance).
  Portable, no hooks: the agent appends to the journal via script, `--distill`
  collects it. `--since` provides idempotency. Automating observation (a Stop
  hook auto-`--log-signal`) is provided by the optional phase 3 (L2).
- **Phase 3 (proposed, requires user opt-in):** harness event hooks
  (UserPromptSubmit / PreToolUse / Stop) for deterministic triggering, JIT
  injection, and auto-capture. Configured via settings.json (the update-config
  skill). Trade-off: coupling to Claude Code + operational complexity.

## Consequences

- **+** The core remains portable; determinism is added in layers, not by
  rewriting.
- **+** Token cost scales with relevance, not with the size of the growing graph.
- **+** Rules are enforceable (`--validate`), not just stated in the prompt.
- **-** Maximum reliability of triggering/capture (phase 3) requires harness
  hooks and opt-in — outside the portable core.
- **-** More commands/surface area in `build.py` (mitigated by the shared
  `iter_claims()` and self-documenting `--help`).

## References

- `persona.md` — LEARN workflow, Recognition, Self-learning protocol (operational source of truth)
- `README.md` §Self-Learning — layers, FSM, extension points (architecture documentation)
- `build.py` — `--validate`, `--claims`, `--candidates`, `--log-signal`, `--distill`, `iter_claims()`
