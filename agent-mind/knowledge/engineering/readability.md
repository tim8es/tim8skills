---
domain: readability
cluster: engineering
summary: "Code readability and clarity: reader-first optimization, cognitive load minimization, why-comments, and consistency within a codebase"
tags: [readability, cognitive-load, comments, clarity, consistency, reader-first]
updated: 2026-06-27
related:
  # code-design owns the code-design->readability (enables) edge (unidirectional)
  - domain: engineering/naming
    type: supports
    edge: "Good names are the primary readability tool; R* claims reinforce what naming starts"
  - domain: engineering/maintainability
    type: supports
    edge: "Reader-first code (R1) and low cognitive load (R2) are prerequisites for safe, confident refactoring"
---

# Readability

## [eng.R1] Optimize for the reader, not the writer
**Confidence**: high
**Severity**: minor
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Clean Code; Code Complete
**Trigger**: Code uses a clever trick, nested ternary, or compressed expression that requires mental effort to decode — even if correct and concise.
**Directive**: Rewrite for the reader. Expand the expression, introduce an intermediate variable with a descriptive name, or add a why-comment. Cleverness that needs decoding is a maintenance cost.
**Because**: Code is read ~10× more often than written. The dominant lifetime cost is comprehension during change. (readability)
**Smells**: One-liner pride; nested ternaries 3+ deep; clever bit-manipulation without a comment; "look how short this is."
**When not**: Idiomatic patterns the team knows well (list comprehensions, null coalescing) — don't expand what is genuinely readable.
**See also**: [eng.R2], [eng.R3]

## [eng.R2] Minimize cognitive load — enable local reasoning
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: A Philosophy of Software Design; "The Programmer's Brain" (Hermans)
**Trigger**: Understanding a piece of code requires knowing the state of a distant variable, the contents of another file, or the execution history of previous calls.
**Directive**: Move related facts closer together. Extract distant dependencies into parameters. Prefer immutable state. Reduce the number of things a reader must hold in their head to safely edit a line.
**Because**: Bounded working memory is the real constraint on safe change; fewer external facts = safer edits. (readability + maintainability)
**Smells**: Action-at-a-distance; state mutated far from where it's read; behavior depending on call order.
**When not**: Dependency injection containers where the indirection is explicit and well-documented.
**See also**: [eng.F4], [eng.F5], [eng.R1]

## [eng.R3] Comments explain WHY, not WHAT
**Confidence**: high
**Severity**: style
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Clean Code Ch.4; Code Complete
**Trigger**: A comment narrates what the code does rather than why — the comment could be derived by reading the code itself.
**Directive**: Delete what-comments. Write why-comments: the intent, the constraint, the non-obvious reason. Example: `// retry: vendor API silently drops the first request after idle timeout`.
**Because**: What-comments rot and lie when code changes; why-comments capture context the code physically cannot express. (maintainability)
**Smells**: `// increment i` above `i++`; commented-out code left in place; docstrings that restate the function name.
**When not**: Public API docstrings where what-documentation is expected by consumers.
**See also**: [eng.R1]

## [eng.R4] Consistency within a codebase
**Confidence**: high
**Severity**: minor
**Context**: general
**Updated**: 2026-06-25
**Evidence**: A Philosophy of Software Design Ch.17; Google style guides
**Trigger**: A new piece of code introduces a different convention or style than the surrounding codebase — even if the new way is objectively better.
**Directive**: Match surrounding conventions. Raise the convention change as a separate decision; don't introduce inconsistency in a feature PR.
**Because**: Consistency lets readers predict; predictability lowers cognitive load across the entire codebase. (readability + maintainability)
**Smells**: One file in a different style; mixed naming schemes; a reinvented utility that duplicates an existing one.
**When not**: When the existing convention is a clear bug or security issue — fix it, but in a dedicated PR.
**See also**: [eng.R2]

## Internal relationships
[eng.R1] --supports--> [eng.R2]   reader-first optimization directly reduces cognitive load
[eng.R4] --supports--> [eng.R2]   consistency helps readers predict, further reducing cognitive load
[eng.R3] --supports--> [eng.R1]   why-comments serve the reader without narrating the obvious
