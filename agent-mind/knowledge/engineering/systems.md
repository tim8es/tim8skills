---
domain: systems
cluster: engineering
summary: "Systems patterns and conventions: separation of concerns, composition over inheritance, Law of Demeter, idempotency, explicit over implicit, observability, fail-fast at startup, semver, conventional commits, API consistency, dependency hygiene"
tags: [separation-of-concerns, idempotency, observability, logging, semver, API, dependencies, composition, inheritance, explicit]
updated: 2026-06-25
related:
  # architecture and security own their edges with systems (unidirectional)
  - domain: engineering/maintainability
    type: supports
    edge: "SE6 observability and SE7 fail-fast make errors visible early (M5) across system boundaries"
  - domain: engineering/code-design
    type: tension
    edge: "⚠ SE5 explicit-over-implicit can produce verbose wiring — balance traceability against KISS (A1)"
---

# Systems & Engineering Patterns

## [eng.SE1] Separate concerns — one reason to change per layer
**Confidence**: high
**Severity**: critical
**Context**: web-backend, api, microservices
**Updated**: 2026-06-25
**Evidence**: Dijkstra (1974); Clean Architecture; Layered Architecture canon
**Trigger**: Presentation logic (HTTP handling, serialization) and business logic coexist in the same function or class, or a domain model contains persistence or formatting logic.
**Directive**: Separate the layers. Route handlers handle HTTP and delegate to services. Services contain business rules and delegate to repositories. Domain models contain business state — not SQL, not JSON serialization.
**Because**: Mixed concerns couple unrelated reasons to change. Separated layers evolve independently. (maintainability + scaling)
**Smells**: SQL queries in route handlers; JSON serialization in domain models; `if (format === 'csv')` inside business logic.
**When not**: Simple CRUD endpoints where a full layered architecture adds more overhead than the codebase warrants.
**See also**: [eng.SE2], [eng.SE5]

## [eng.SE2] Prefer composition over inheritance
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: GoF Design Patterns; Effective Java Item 18
**Trigger**: A class hierarchy is deeper than 2 levels, a subclass overrides a method only to disable it, or a superclass change breaks subclasses unexpectedly.
**Directive**: Replace inheritance with composition. Extract the behavior into a focused component and inject it. Make dependencies explicit rather than inherited.
**Because**: Inheritance couples a subclass to superclass internals. Deep hierarchies spread behavior across a tree that is difficult to trace and test in isolation. (maintainability)
**Smells**: Class hierarchy >2 levels deep; a subclass overriding a method to make it a no-op; "you can't understand the subclass without reading the whole hierarchy."
**When not**: When inheritance models a genuine IS-A relationship and the hierarchy is shallow and stable.
**See also**: [eng.SE1]

## [eng.SE3] Tell objects what to do — don't query their state
**Confidence**: high
**Severity**: minor
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Pragmatic Programmer; Law of Demeter (Lieberherr & Holland, 1989)
**Trigger**: Code chains multiple method calls on the result of another call: `order.getCustomer().getAddress().getCity()` — or external logic makes decisions based on an object's internal state that the object itself should make.
**Directive**: Move the logic into the object that owns the data. Ask for a result, not for data to compute a result from. One dot, not a chain.
**Because**: Long chains create hidden coupling to intermediate types. When any intermediate changes, all chains break. (maintainability)
**Smells**: `a.getB().getC().doSomething()`; feature envy; business logic outside the object that should own it.
**When not**: Fluent builder APIs where the chain is the intended interface and intermediate objects are not domain objects.
**See also**: [eng.SE1]

## [eng.SE4] Make cross-boundary operations idempotent
**Confidence**: high
**Severity**: critical
**Context**: web-backend, api, microservices
**Updated**: 2026-06-25
**Evidence**: Designing Data-Intensive Applications (Kleppmann); Stripe/AWS API design docs
**Trigger**: An operation crossing a network or queue boundary is not safe to retry — running it twice would produce duplicate side effects (double charge, duplicate email).
**Directive**: Add an idempotency key. On retry with the same key, return the original result without re-executing. Design consumers to deduplicate events by ID.
**Because**: Networks fail and retries are inevitable. Non-idempotent retries turn a transient failure into a data integrity incident. (reliability)
**Smells**: Payment endpoint without idempotency key; event consumers that process every message regardless of duplicates.
**When not**: Read-only operations — GET requests are inherently idempotent.
**See also**: [eng.SE7]

## [eng.SE5] Prefer explicit wiring over magic
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Zen of Python ("explicit is better than implicit"); 12-factor app
**Trigger**: Behavior is determined by file naming, directory structure, convention, or a global registry — and changing behavior requires knowing the convention rather than following the code.
**Directive**: Make dependencies and behavior explicit: pass them as parameters, declare them at the composition root, make them traceable by reading the source.
**Because**: Implicit coupling is invisible until it breaks; explicit coupling is traceable at read time. (readability + maintainability)
**Smells**: Auto-wiring by convention with no declaration; behavior changing based on file naming; global event buses as primary communication.
**When not**: Well-established framework conventions (Rails routes, Spring annotations) where the team knows the magic and the overhead of explicitness exceeds the benefit.
**See also**: [eng.SE1]

## [eng.SE6] Instrument for observability from the start
**Confidence**: high
**Severity**: major
**Context**: web-backend, api, microservices
**Updated**: 2026-06-25
**Evidence**: Google SRE Book; "Observability Engineering" (Majors et al.)
**Trigger**: A service is being built without structured logs, meaningful metrics, or distributed trace context — or observability is being deferred.
**Directive**: Add structured logging, metrics, and trace context from day one. Log meaningful business events, not just errors. Include correlation IDs. Use structured (JSON) logs.
**Because**: You cannot debug in production what you cannot observe. Retrofitting observability is expensive and always incomplete. (maintainability + operations)
**Smells**: `console.log("here")`; no request/correlation IDs; metrics added only after an outage; free-text logs that can't be queried.
**When not**: CLI scripts and batch jobs where structured logging overhead exceeds the benefit.
**See also**: [eng.SE7]

## [eng.SE7] Fail fast at startup — validate configuration before serving
**Confidence**: high
**Severity**: major
**Context**: web-backend, api, microservices
**Updated**: 2026-06-25
**Evidence**: Pragmatic Programmer ("dead programs tell no lies"); 12-factor app Config
**Trigger**: Required configuration (env vars, secrets, DB connections) is read lazily — deep inside request handling — rather than validated at startup.
**Directive**: Validate all required configuration at startup before the service accepts any traffic. If required config is missing or malformed, exit immediately with a clear error.
**Because**: Early failure is cheap and obvious; late failure under load is a production incident with unclear cause. (reliability + security)
**Smells**: Config read inline in a request handler; DB connection created on first use; "it only fails when it tries to do X."
**When not**: Lambda/serverless functions where startup cost must be minimized — but at minimum validate critical secrets on cold start.
**See also**: [eng.SE4], [eng.SE6]

## [eng.CV1] Communicate breaking changes through version numbers
**Confidence**: high
**Severity**: major
**Context**: library, api
**Updated**: 2026-06-25
**Evidence**: semver.org; npm/Cargo/pip ecosystem
**Trigger**: A public API has a breaking change in a minor or patch release, or MAJOR is bumped for a non-breaking change.
**Directive**: MAJOR for breaking changes. MINOR for new backward-compatible capabilities. PATCH for bug fixes. Treat version numbers as a communication contract.
**Because**: Callers rely on version signals to manage upgrade risk. Breaking semver destroys trust and breaks automated dependency management. (conventions)
**Smells**: Breaking change in a patch release; `v2.0.0` for a trivial addition; "just check the changelog."
**When not**: Internal libraries with a single consumer where semver adds overhead without benefit.
**See also**: [eng.CV4]

## [eng.CV2] Write structured commit messages
**Confidence**: high
**Severity**: minor
**Context**: general
**Updated**: 2026-06-25
**Evidence**: conventionalcommits.org; Angular commit convention
**Trigger**: A commit message uses vague language: "wip", "fix", "stuff", "misc changes."
**Directive**: Use conventional commits: `feat(scope): what and why`, `fix(scope): what and why`. Breaking changes in footer as `BREAKING CHANGE:`. One logical change per commit.
**Because**: Structured messages enable automated changelogs, semantic-release, and instant intent communication in `git log`. (conventions + process)
**Smells**: "wip", "stuff", "fix", "updates"; messages describing implementation rather than intent.
**When not**: Personal/experimental branches where commit quality matters less — but squash before merging.
**See also**: [eng.CV1]

## [eng.CV3] Follow HTTP verb semantics and consistent API conventions
**Confidence**: high
**Severity**: major
**Context**: api, web-backend
**Updated**: 2026-06-25
**Evidence**: Google API Design Guide; REST constraints (Fielding, 2000)
**Trigger**: An API endpoint uses the wrong HTTP verb, uses inconsistent resource naming, or returns different error shapes from different endpoints.
**Directive**: GET = safe + idempotent (never mutates). POST = create. PUT/PATCH = update. DELETE = remove. Resources = plural nouns. Errors = consistent shape.
**Because**: API consistency lets consumers build accurate mental models. Inconsistency forces per-endpoint documentation and produces integration bugs. (conventions)
**Smells**: GET that mutates; POST for reads; mixed `snake_case`/`camelCase` in same API; different error formats from different endpoints.
**When not**: GraphQL or RPC APIs where REST conventions don't apply — but internal consistency still matters.
**See also**: [eng.SE4]

## [eng.CV4] Pin dependency versions and audit regularly
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Supply-chain security; npm/pip audit docs
**Trigger**: Dependencies are unpinned (`*`, `^` without lock file), or third-party packages imported for functionality available in stdlib.
**Directive**: Pin exact versions in lock files. Commit the lock file. Run `npm audit`/`pip audit` in CI. Prefer stdlib for simple utilities over adding a dependency.
**Because**: Unpinned deps cause surprise breakage. Each dependency is a maintenance obligation and potential supply-chain attack vector. (maintainability + security)
**Smells**: `"lodash": "*"`; no lock file; importing a package for a single 10-line utility; unreviewed transitive dependencies.
**When not**: Lock files for published libraries (use ranges instead) — but pin in applications.
**See also**: [eng.CV1]

## Internal relationships
[eng.SE1] --enables-->  [eng.SE5]  separated layers make explicit wiring practical to implement
[eng.SE2] --supports--> [eng.SE1]  composition makes separation of concerns implementable
[eng.SE3] --supports--> [eng.SE1]  tell-don't-ask enforces layer separation at the method level
[eng.SE6] --supports--> [eng.SE7]  observability helps verify startup validation is working correctly
[eng.CV4] --supports--> [eng.SE7]  pinned deps make startup validation reliable and reproducible
[eng.CV1] --supports--> [eng.CV4]  semver makes dependency pinning meaningful
[eng.SE4] --supports--> [eng.SE6]  idempotency keys appear in logs and are essential for debugging retries
