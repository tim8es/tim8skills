---
domain: maintainability
cluster: engineering
summary: "DRY knowledge not text, avoid premature abstraction (rule of three), YAGNI, high cohesion low coupling, visible errors at right level, Boy Scout rule, tests, small changes, review for correctness not taste"
tags: [DRY, YAGNI, coupling, cohesion, refactoring, tests, code-review, abstraction, boy-scout, technical-debt]
updated: 2026-06-27
related:
  # code-design owns the code-design->maintainability (enables) edge (unidirectional)
  - domain: engineering/architecture
    type: enables
    edge: "Low coupling (M4) is what lets architectural boundaries (A3) stay stable"
  - domain: engineering/security
    type: tension
    edge: "⚠ Visible errors for debugging (M5) vs secure messages for users (S5): detail to internal logs, generic to callers"
---

# Maintainability & Change

## [eng.M1] DRY — deduplicate knowledge, not text
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: The Pragmatic Programmer
**Trigger**: The same *decision* — a business rule, formula, validation logic, or constant — appears in multiple places and would need to change together.
**Directive**: Extract a single authoritative representation. Two identical code lines representing *different* decisions are not a violation — don't extract them.
**Because**: Duplicated knowledge drifts; a fix in one copy missed in another is a latent bug. (maintainability)
**Smells**: Same business rule in multiple files; a constant defined in three places; copy-pasted logic that must always change together.
**When not**: Infrastructure-layer duplication that intentionally isolates layers from each other.
**See also**: [eng.M2], [eng.M4]

## [eng.M2] Wait for the third repetition before abstracting
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Sandi Metz ("duplication is cheaper than the wrong abstraction"); AHA principle
**Trigger**: Two pieces of code look similar and there's an impulse to extract a shared abstraction after seeing only 1–2 occurrences.
**Directive**: Tolerate the duplication until the same *decision* repeats ~3× and all callers genuinely share the same reason to change.
**Because**: A premature abstraction couples unrelated callers; removing the wrong abstraction later is expensive and risky. (maintainability)
**Smells**: A "shared" helper with a growing flags-soup signature; an abstraction where every caller passes different overrides.
**When not**: Obvious, stable patterns (e.g. error handling wrappers) where the abstraction is clearly right from the first use.
**See also**: [eng.M1]

## [eng.M3] YAGNI — implement only what is needed now
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Extreme Programming; Pragmatic Programmer
**Trigger**: Code adds generality, config options, or extension points for requirements that don't exist yet.
**Directive**: Remove speculative features. Implement only what current concrete requirements demand.
**Because**: Speculative code is written, tested, documented, and maintained forever — usually for a future that never arrives. (maintainability + efficiency)
**Smells**: Unused parameters "for future use"; plugin systems with one plugin; deep config for a single deployment.
**When not**: Explicitly planned near-term features where the extension point costs little and avoids a breaking change later.
**See also**: [eng.M2]

## [eng.M4] High cohesion, low coupling
**Confidence**: high
**Severity**: critical
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Structured Design (Constantine & Yourdon); Clean Architecture
**Trigger**: A single logical change requires edits to many unrelated files (shotgun surgery), or a module imports dependencies from across the entire application.
**Directive**: Co-locate code that changes for the same reason. Break dependencies between code that changes for different reasons.
**Because**: This is what makes changes local instead of cascades — the single best predictor of how painful future changes will be. (maintainability + scaling)
**Smells**: One feature change touches 8 files; a "utility" module imported by everything; a class that exists only to call methods on another class.
**When not**: N/A — coupling and cohesion are always relevant; the question is the right level of granularity.
**See also**: [eng.M1]

## [eng.M5] Make errors visible — handle at the right level
**Confidence**: high
**Severity**: critical
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Pragmatic Programmer ("dead programs tell no lies"); Effective Java Ch.10
**Trigger**: An error is caught and silenced, logged without action, or converted to a null/false return that callers are unlikely to check.
**Directive**: Let errors propagate to the layer with enough context to decide. Fail fast on programmer errors. For expected failures, handle explicitly — don't silently convert to null returns.
**Because**: Silent failures turn one bug into a long debugging session. (maintainability)
**Smells**: Empty catch blocks; `return null` on error; `log.error(e)` with no rethrow; a boolean success flag nobody checks.
**When not**: Boundary layers (API, UI) where errors must be translated to user-facing responses — handle there, log internally.
**See also**: [eng.M4]

## [eng.M6] Leave it cleaner than you found it
**Confidence**: high
**Severity**: style
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Clean Code (Boy Scout Rule); Refactoring (Fowler)
**Trigger**: While editing a file, a small, clearly improvable issue is visible adjacent to the current change.
**Directive**: Fix it as part of the change. Keep the improvement in-scope and small. Don't launch a refactoring expedition — just leave the campsite better.
**Because**: Entropy is continuous; small distributed cleanup prevents slow degradation into code nobody wants to touch. (maintainability)
**Smells**: `// TODO: clean this up` untouched for years; a file everyone is afraid to edit.
**When not**: Issues that require a separate PR or architectural decisions — track them, don't fix them inline.
**See also**: [eng.M8]

## [eng.M7] Tests as safety net and executable spec
**Confidence**: high
**Severity**: critical
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Pragmatic Programmer; Working Effectively with Legacy Code (Feathers)
**Trigger**: Code is being changed and there are no tests covering the affected behavior, or tests assert implementation details rather than observable outcomes.
**Directive**: Before refactoring untested code, write characterization tests to capture its current behavior. Test behavior, not implementation.
**Because**: Tests make refactoring fearless. They document intended behavior in a form that can't silently go stale without failing. (maintainability)
**Smells**: No tests around code being changed; tests asserting private fields; a suite that breaks on internal refactors.
**When not**: Exploratory spikes, throwaway scripts — but production code always needs test coverage before change.
**See also**: [eng.M6], [eng.M8]

## [eng.M8] Small, reviewable changes
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Google Engineering Practices
**Trigger**: A PR mixes multiple logical changes, exceeds ~400 lines of diff, or has a commit message like "misc fixes" or "wip."
**Directive**: Split into separate, self-contained PRs — one logical change each. Write a commit message that describes what and why.
**Because**: Small diffs get better review, bisect cleanly on failure, and roll back safely. Core lever of sustained velocity. (maintainability + process)
**Smells**: 1000-line PRs; "misc fixes" commit messages; unrelated changes bundled together.
**When not**: Large atomic operations (mass rename, dependency upgrade, generated code sync) where splitting would leave the codebase in a broken intermediate state — keep them atomic but still scoped to a single logical operation.
**See also**: [eng.M7], [eng.M6]

## [eng.M9] Review for correctness and clarity, not taste
**Confidence**: high
**Severity**: minor
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Google Code Review Developer Guide
**Trigger**: A code review comment addresses a personal style preference rather than a real correctness, security, or maintainability concern.
**Directive**: Mark it as `Nit:` explicitly and make it non-blocking. Reserve blocking feedback for actual defects. Automate style with a linter.
**Because**: Conflating taste with correctness slows teams and trains authors to dismiss all feedback — including the important kind. (process)
**Smells**: Blocking a PR on naming preference; bikeshedding on formatting; vague "I'd do it differently" without naming a risk.
**When not**: N/A — severity discipline applies universally in code review.
**See also**: [eng.M8]

## Internal relationships
[eng.M7] --enables-->  [eng.M6]   tests make small improvements safe to apply
[eng.M8] --supports--> [eng.M6]   small changes = safe incremental cleanup
[eng.M4] --enables-->  [eng.M1]   low coupling makes a single source of truth achievable
[eng.M1] <--tension--> [eng.M2]   deduplicate knowledge vs wait for third repetition
[eng.M3] <--tension--> [eng.M4]   YAGNI vs cohesion: don't build speculative, but co-locate what changes together
[eng.M9] --supports--> [eng.M8]   severity discipline makes small PRs reviewable faster
