# Cross-domain and claim-level edges
_Generated from `related:` fields and `## Internal relationships` sections._
_Edit source domain files, not this file._

## Domain — reinforcing
```
  engineering/architecture           --supports-->    engineering/systems                SE1 separation of concerns is A2 dependency inversion applied at the layer level
  engineering/code-design            --enables-->     engineering/maintainability        Single-purpose functions (F1) are the prerequisite for testable, changeable units
  engineering/code-design            --enables-->     engineering/readability            F4 deep modules and F5 no side effects are structural prerequisites that enable local reasoning [eng.R2]
  engineering/code-design            --supports-->    engineering/naming                 Good names make function signatures self-documenting
  engineering/maintainability        --enables-->     engineering/architecture           Low coupling (M4) is what lets architectural boundaries (A3) stay stable
  engineering/naming                 --supports-->    engineering/maintainability        Consistent naming lowers the cost of reading unfamiliar code during change
  engineering/performance            --supports-->    engineering/systems                SE4 idempotency and SE6 observability are prerequisites for safe production performance tuning
  engineering/readability            --supports-->    engineering/maintainability        Reader-first code (R1) and low cognitive load (R2) are prerequisites for safe, confident refactoring
  engineering/readability            --supports-->    engineering/naming                 Good names are the primary readability tool; R* claims reinforce what naming starts
  engineering/security               --supports-->    engineering/architecture           Stable contracts (A3) make security validation points explicit and auditable
  engineering/security               --supports-->    engineering/systems                SE7 fail-fast at startup catches misconfigured secrets before serving traffic
  engineering/systems                --supports-->    engineering/maintainability        SE6 observability and SE7 fail-fast make errors visible early (M5) across system boundaries
```

## Domain — tension ⚠  (name the trade-off when these domains meet)
```
  engineering/architecture           <--tension-->    engineering/code-design            ⚠ A1 KISS vs A2 DIP: a single-implementation interface may be ceremony — add seam only when a second impl is real
  engineering/architecture           <--tension-->    engineering/performance            ⚠ A4 measure-before-optimizing: simplicity first, targeted optimization only with profile data
  engineering/code-design            <--tension-->    engineering/performance            ⚠ Optimized hot-path code often sacrifices readability — only trade clarity on a measured bottleneck
  engineering/maintainability        <--tension-->    engineering/security               ⚠ Visible errors for debugging (M5) vs secure messages for users (S5): detail to internal logs, generic to callers
  engineering/systems                <--tension-->    engineering/code-design            ⚠ SE5 explicit-over-implicit can produce verbose wiring — balance traceability against KISS (A1)
```

## Claim-level — reinforcing
```
  [eng.A2]     --enables-->     [eng.A3]     depending on abstractions makes boundary contracts stable
  [eng.A2]     --supports-->    [eng.A5]     abstract interfaces make components replaceable
  [eng.A4]     --supports-->    [eng.A1]     measure-first supports KISS: don't add complexity for unmeasured gains
  [eng.A5]     --supports-->    [eng.A3]     design for deletion requires stable contracts at every boundary
  [eng.CV1]     --supports-->    [eng.CV4]     semver makes dependency pinning meaningful
  [eng.CV4]     --supports-->    [eng.SE7]     pinned deps make startup validation reliable and reproducible
  [eng.F1]     --enables-->     [eng.F2]     single-purpose functions are easier to separate into commands vs queries
  [eng.F2]     --supports-->    [eng.F5]     CQS prevents hidden side effects in queries
  [eng.F4]     --supports-->    [eng.R2]     deep modules reduce cognitive load: fewer public things to learn
  [eng.F5]     --supports-->    [eng.R2]     no hidden effects = local reasoning holds completely
  [eng.M4]     --enables-->     [eng.M1]     low coupling makes a single source of truth achievable
  [eng.M7]     --enables-->     [eng.M6]     tests make small improvements safe to apply
  [eng.M8]     --supports-->    [eng.M6]     small changes = safe incremental cleanup
  [eng.M9]     --supports-->    [eng.M8]     severity discipline makes small PRs reviewable faster
  [eng.N2]     --refines-->     [eng.N1]     booleans-as-questions is a specific case of nouns-for-data
  [eng.N3]     --refines-->     [eng.N1]     SHOUT constants are a specific case of nouns-for-data
  [eng.N4]     --supports-->    [eng.N5]     English identifiers are clearer to a wider audience
  [eng.N6]     --refines-->     [eng.N5]     removing filler is a specific application of clarity-over-brevity
  [eng.P1]     --supports-->    [eng.P7]     algorithm fixes are easy to understand; micro-opts always need documentation
  [eng.P3]     --supports-->    [eng.P2]     minimizing allocations also improves cache utilization
  [eng.P4]     --supports-->    [eng.P5]     batching and lazy evaluation are complementary: reduce and defer I/O
  [eng.P6]     --supports-->    [eng.P4]     async I/O enables batching without blocking
  [eng.R1]     --supports-->    [eng.R2]     reader-first optimization directly reduces cognitive load
  [eng.R3]     --supports-->    [eng.R1]     why-comments serve the reader without narrating the obvious
  [eng.R4]     --supports-->    [eng.R2]     consistency helps readers predict, further reducing cognitive load
  [eng.S1]     --enables-->     [eng.S2]     must validate at boundary before parameterizing makes sense
  [eng.S1]     --enables-->     [eng.S5]     boundary validation is a prerequisite for knowing what to deny
  [eng.S3]     --supports-->    [eng.S4]     least privilege is one concrete layer in defense in depth
  [eng.S4]     --supports-->    [eng.S5]     multiple layers include failing securely as one of them
  [eng.S6]     --supports-->    [eng.S3]     removing secrets from code is part of minimizing privilege surface
  [eng.S7]     --supports-->    [eng.S5]     standard crypto fails securely; custom crypto fails unpredictably
  [eng.S8]     --supports-->    [eng.S3]     smaller attack surface = fewer permissions needed
  [eng.S8]     --supports-->    [eng.S4]     fewer exposed capabilities = fewer layers to defend
  [eng.SE1]     --enables-->     [eng.SE5]     separated layers make explicit wiring practical to implement
  [eng.SE2]     --supports-->    [eng.SE1]     composition makes separation of concerns implementable
  [eng.SE3]     --supports-->    [eng.SE1]     tell-don't-ask enforces layer separation at the method level
  [eng.SE4]     --supports-->    [eng.SE6]     idempotency keys appear in logs and are essential for debugging retries
  [eng.SE6]     --supports-->    [eng.SE7]     observability helps verify startup validation is working correctly
```

## Claim-level — tension ⚠
```
  [eng.A1]     <--tension-->    [eng.A2]     KISS vs DIP: one-impl interface may be pure ceremony
  [eng.M1]     <--tension-->    [eng.M2]     deduplicate knowledge vs wait for third repetition
  [eng.M3]     <--tension-->    [eng.M4]     YAGNI vs cohesion: don't build speculative, but co-locate what changes together
```
