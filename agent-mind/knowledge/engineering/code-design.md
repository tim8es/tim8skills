---
domain: code-design
cluster: engineering
summary: "Function design: single responsibility, CQS, parameter discipline, deep modules, no surprising side effects"
tags: [functions, CQS, side-effects, abstraction, single-responsibility, parameters]
updated: 2026-06-27
related:
  - domain: engineering/maintainability
    type: enables
    edge: "Single-purpose functions (F1) are the prerequisite for testable, changeable units"
  - domain: engineering/performance
    type: tension
    edge: "⚠ Optimized hot-path code often sacrifices readability — only trade clarity on a measured bottleneck"
  - domain: engineering/naming
    type: supports
    edge: "Good names make function signatures self-documenting"
  - domain: engineering/readability
    type: enables
    edge: "F4 deep modules and F5 no side effects are structural prerequisites that enable local reasoning [eng.R2]"
---

# Code Design

## [eng.F1] One job per function
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Clean Code Ch.3; SOLID SRP at function scope
**Trigger**: A function can be described only by using "and" — it validates *and* transforms *and* persists. Or it mixes high-level orchestration with low-level implementation detail.
**Directive**: Extract each responsibility into its own function with a descriptive name.
**Because**: Single-purpose units are nameable, testable, reusable; they localize change to the smallest surface. (maintainability + readability)
**Smells**: "and" in the function's description; functions longer than one screen; mixed abstraction levels in one body.
**When not**: Short, obviously-single-purpose functions where extraction would create unnecessary indirection.
**See also**: [eng.F2], [eng.F4]

## [eng.F2] Command/query separation
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Pragmatic Programmer; Meyer's CQS
**Trigger**: A function that looks like a query (returns a value, named `getX`/`isX`) also mutates state, writes to I/O, or triggers a side effect.
**Directive**: Split into a pure query (returns value, no side effects) and a separate command (mutates state, returns void/status).
**Because**: Callers reason about queries as side-effect-free; hidden mutation in a query is a classic source of subtle bugs. (readability)
**Smells**: `getUser()` that also logs or caches; a query whose call order changes program state.
**When not**: Builder pattern where chained setters return `this` — idiomatic and well-understood.
**See also**: [eng.F1], [eng.F5]

## [eng.F3] Few parameters, no boolean flags
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Clean Code Ch.3
**Trigger**: A function has 3+ positional parameters, or a boolean literal (`true`/`false`) appears at a call site.
**Directive**: For boolean flags — split into two named functions or replace with an enum/options object. For many params — introduce a parameter object.
**Because**: `render(true)` is unreadable without an IDE. A long parameter list signals a missing abstraction. (readability)
**Smells**: `createUser(name, email, true, false, null)`; literal `true`/`false` at call sites; parameter ordering bugs.
**When not**: Math/algorithm functions with well-known multi-param signatures (`lerp(a, b, t)`).
**See also**: [eng.F1]

## [eng.F4] Deep modules, simple interfaces
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: A Philosophy of Software Design Ch.4
**Trigger**: A module or class exposes nearly as many public methods as it has lines of implementation, or a wrapper function adds no logic beyond forwarding arguments.
**Directive**: Hide complexity behind the narrowest interface that serves callers. Move decision logic inside; expose only what callers genuinely need to control.
**Because**: The interface is the cost every caller pays forever; depth is the value. Shallow modules add ceremony without hiding complexity. (maintainability + scaling)
**Smells**: Pass-through wrappers; classes that are mostly getters/setters; interface surface ≈ implementation size.
**When not**: Adapter/facade patterns where the shallow surface is intentional for compatibility.
**See also**: [eng.F1], [eng.R2]

## [eng.F5] No surprising side effects
**Confidence**: high
**Severity**: critical
**Context**: general
**Updated**: 2026-06-25
**Evidence**: A Philosophy of Software Design ("obvious code"); Pragmatic Programmer
**Trigger**: A function's name and signature suggest it is pure or read-only, but it performs I/O, mutates global state, or produces results depending on hidden state.
**Directive**: Remove the hidden effect, or make it explicit in the function's name and signature.
**Because**: Hidden effects break local reasoning — callers cannot understand code without reading its full implementation. (readability + maintainability)
**Smells**: `init()` that opens a network socket; a getter that caches with a side effect; "pure" function touching module-level state.
**When not**: N/A — hidden side effects are never acceptable; the question is only how to surface them.
**See also**: [eng.F2], [eng.R2]

## Internal relationships
[eng.F1] --enables-->  [eng.F2]   single-purpose functions are easier to separate into commands vs queries
[eng.F2] --supports--> [eng.F5]   CQS prevents hidden side effects in queries
[eng.F4] --supports--> [eng.R2]   deep modules reduce cognitive load: fewer public things to learn
[eng.F5] --supports--> [eng.R2]   no hidden effects = local reasoning holds completely
