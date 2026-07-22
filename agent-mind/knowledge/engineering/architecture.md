---
domain: architecture
cluster: engineering
summary: "KISS, dependency inversion, stable contracts at boundaries, measure before optimizing, design for deletion"
tags: [KISS, DIP, contracts, boundaries, design-patterns, abstraction, dependency-inversion, modularity]
updated: 2026-06-25
related:
  # maintainability owns the maintainability->architecture (enables) edge (unidirectional)
  - domain: engineering/performance
    type: tension
    edge: "⚠ A4 measure-before-optimizing: simplicity first, targeted optimization only with profile data"
  - domain: engineering/code-design
    type: tension
    edge: "⚠ A1 KISS vs A2 DIP: a single-implementation interface may be ceremony — add seam only when a second impl is real"
  - domain: engineering/systems
    type: supports
    edge: "SE1 separation of concerns is A2 dependency inversion applied at the layer level"
---

# Architecture & Scaling

## [eng.A1] KISS — resist complexity that hasn't earned its place
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: A Philosophy of Software Design Ch.1–2; Worse Is Better (Gabriel)
**Trigger**: A design introduces layers, abstractions, or patterns beyond what current concrete requirements demand.
**Directive**: Challenge every layer: what problem does it solve *right now*? Remove what can't be justified. Complexity must earn its place with a specific, present benefit.
**Because**: Complexity compounds — each added layer multiplies surfaces for bugs, onboarding cost, and change cost. (maintainability + scaling)
**Smells**: Patterns applied for their own sake; layers that only delegate; abstractions with a single permanent implementation.
**When not**: When future requirements are contractually committed and the extension point costs little now.
**See also**: [eng.A2], [eng.A5]

## [eng.A2] Depend on abstractions — point dependencies inward
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: SOLID Dependency Inversion Principle; Clean Architecture (Martin)
**Trigger**: Business logic or domain code imports infrastructure details directly — an ORM, HTTP client, a specific vendor SDK, or a UI framework.
**Directive**: Invert the dependency: define an interface or abstraction in the domain layer; implement it in the infrastructure layer. Domain depends on the abstraction; infrastructure depends on nothing from the domain.
**Because**: Lets you swap infrastructure and test domain logic in isolation without any infrastructure running. (scaling + maintainability)
**Smells**: `import sequelize` inside a business rule; domain tests requiring a real database; UI framework types in business logic.
**When not**: Small scripts, CLIs, or prototypes where the overhead of inversion exceeds the benefit.
**See also**: [eng.A1], [eng.A3]

## [eng.A3] Stable contracts at boundaries
**Confidence**: high
**Severity**: critical
**Context**: api, microservices, library
**Updated**: 2026-06-25
**Evidence**: Clean Architecture; Google API Design Guide
**Trigger**: An internal refactor changes the interface exposed to callers — or a module leaks internal types through its public surface.
**Directive**: Keep public interfaces minimal and explicitly versioned. Internal changes must not break callers. When a contract must change, do it with a migration path.
**Because**: Independent teams and deploys are only possible when contracts are stable. Leaking internals makes every internal refactor a cross-team coordination event. (scaling)
**Smells**: Internal DB model types in API responses; breaking changes in a minor version; "just update all the callers" as a refactor strategy.
**When not**: Internal module boundaries within a single team/codebase where coupling is intentional and short-lived.
**See also**: [eng.A2], [eng.A5]

## [eng.A4] Measure before optimizing
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Knuth; Code Complete Ch.25
**Trigger**: A proposed change sacrifices clarity, simplicity, or correctness for performance without profile data showing the target code is a bottleneck.
**Directive**: Reject the optimization until there is measurement. Write clear code first; profile; then optimize only the proven hot path.
**Because**: Most code is not on the critical path. Premature optimization sacrifices clarity for speed that is unmeasurable, in code that runs rarely. (efficiency + readability)
**Smells**: Hand-unrolled loops in cold paths; "I made it faster" with no benchmark; complexity introduced "for performance" in error-handling code.
**When not**: Obvious algorithmic improvements (O(n²) → O(n log n)) that are clearly better even without profiling.
**See also**: [eng.A1]

## [eng.A5] Design for deletion and change
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: "Write code that is easy to delete" (tef); microservice practice
**Trigger**: A component is becoming entangled — imported everywhere, referenced in unrelated modules, or is the one thing nobody wants to touch.
**Directive**: Isolate it behind a narrow interface. Minimize its surface. The goal: if requirements change, the component can be replaced without a cascade.
**Because**: Requirements always change. Replaceability over time is more valuable than maximum reuse at a point in time. (scaling)
**Smells**: "We can never change that part"; a utility half the codebase imports; god objects that do everything.
**When not**: Core domain objects that *should* be central — but even these should have narrow interfaces.
**See also**: [eng.A3], [eng.A1]

## Internal relationships
[eng.A2] --enables-->  [eng.A3]   depending on abstractions makes boundary contracts stable
[eng.A2] --supports--> [eng.A5]   abstract interfaces make components replaceable
[eng.A1] <--tension--> [eng.A2]   KISS vs DIP: one-impl interface may be pure ceremony
[eng.A4] --supports--> [eng.A1]   measure-first supports KISS: don't add complexity for unmeasured gains
[eng.A5] --supports--> [eng.A3]   design for deletion requires stable contracts at every boundary
