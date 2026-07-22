---
domain: performance
cluster: engineering
summary: "Algorithm complexity first, cache-friendly memory, minimize allocations in hot paths, batch I/O and eliminate N+1, lazy evaluation, match concurrency to bottleneck, isolate optimizations"
tags: [latency, N+1, cache, memory, concurrency, async, bottleneck, GC, optimization, throughput, performance]
updated: 2026-06-25
related:
  # code-design and architecture own their tension edges with performance (unidirectional)
  - domain: engineering/systems
    type: supports
    edge: "SE4 idempotency and SE6 observability are prerequisites for safe production performance tuning"
---

# Performance & Execution

## [eng.P1] Fix algorithmic complexity before anything else
**Confidence**: high
**Severity**: critical
**Context**: general
**Updated**: 2026-06-25
**Evidence**: CLRS; Knuth
**Trigger**: A performance concern exists and the proposed solution is a micro-optimization while the underlying algorithm or data structure is O(n) or worse for the access pattern.
**Directive**: Address algorithmic complexity first. Replace linear scan with hash lookup, repeated sort with sorted structure, O(n²) comparison with an index.
**Because**: Algorithmic improvements are multiplicative (100× at n=1M); micro-optimizations are additive (2–5×). (efficiency)
**Smells**: Linear scan in a hot loop over a fixed key set; sorting to find a minimum; recomputing inside a loop what could be pre-computed outside.
**When not**: When the dataset is always tiny (n < 100) and simplicity matters more than theoretical complexity.
**See also**: [eng.P7]

## [eng.P2] Access memory sequentially — avoid pointer chasing
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Data-Oriented Design (Ritter); CPU architecture fundamentals
**Trigger**: A performance-sensitive path traverses a linked list, jumps between scattered heap objects, or accesses fields from multiple structs interleaved in memory.
**Directive**: Reorganize data so hot access paths read memory sequentially. Group fields that are accessed together. Prefer arrays over linked lists in hot paths.
**Because**: A cache miss costs ~100× a cache hit. Memory layout dominates performance at scale. (efficiency)
**Smells**: Linked-list traversal in a critical path; a hot loop dereferencing many separate heap pointers.
**When not**: Cold paths, infrequent operations, or data structures where insertion/deletion performance matters more than sequential read.
**See also**: [eng.P3]

## [eng.P3] Minimize allocations in hot paths
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Systems Performance (Gregg); JVM/Go/V8 runtime profiling
**Trigger**: A frequently-called path creates new objects, buffers, or collections on every invocation without reuse.
**Directive**: Measure GC pressure (p99 latency, GC pause metrics). Where allocation is confirmed as a bottleneck, introduce pooling, reuse buffers, or move short-lived allocations to the stack.
**Because**: Each allocation is a potential GC event. GC pauses kill tail latency predictability even when average throughput looks fine. (efficiency)
**Smells**: `new` inside a tight loop; temporary collections per request with no pooling; "fine on average" without checking p99.
**When not**: Cold paths and infrequent operations; languages with compile-time allocation guarantees (Rust, C).
**See also**: [eng.P2]

## [eng.P4] Batch I/O — eliminate N+1
**Confidence**: high
**Severity**: critical
**Context**: web-backend, database, api
**Updated**: 2026-06-25
**Evidence**: Designing Data-Intensive Applications (Kleppmann)
**Trigger**: A loop issues one database query, one HTTP request, or one file read per item in a collection.
**Directive**: Replace with a single bulk operation: `WHERE id IN (...)`, a batch API endpoint, or prefetched related data. Move I/O outside the loop.
**Because**: Network and disk latency dwarfs compute by 3–5 orders of magnitude. N round-trips is never competitive with 1 bulk operation. (efficiency)
**Smells**: A DB query inside a `for` loop; lazy-loaded ORM relationships in a list render; loading items one-by-one where a batch API exists.
**When not**: When data must be fetched strictly sequentially due to dependency on previous results.
**See also**: [eng.P5]

## [eng.P5] Defer and short-circuit — don't compute what you won't use
**Confidence**: high
**Severity**: minor
**Context**: general
**Updated**: 2026-06-25
**Evidence**: General engineering practice
**Trigger**: Code computes a value or makes a call before checking whether the result will actually be used. Or a compound condition evaluates expensive branches before cheap ones.
**Directive**: Reorder conditions cheapest-first. Defer expensive computation until after the condition that gates it.
**Because**: Skipped work costs nothing; this compounds at millions of calls per second. (efficiency)
**Smells**: Building a full response object then checking if the user is authorized; AND/OR conditions with the expensive check first.
**When not**: When the check itself is as expensive as the computation, or when side effects of the check are required.
**See also**: [eng.P4]

## [eng.P6] Match the concurrency model to the actual bottleneck
**Confidence**: high
**Severity**: major
**Context**: web-backend, api, microservices
**Updated**: 2026-06-25
**Evidence**: Node.js/Go/Python async docs; Designing Data-Intensive Applications
**Trigger**: Concurrency is being introduced without profiling to confirm whether the bottleneck is I/O-bound or CPU-bound.
**Directive**: Profile first. I/O-bound → async/event-loop or non-blocking I/O. CPU-bound → true parallelism (threads, processes, worker pools).
**Because**: Async for CPU-bound work still blocks the event loop. Threads for pure I/O add context-switch overhead. Wrong model = cost without gain. (efficiency + maintainability)
**Smells**: Thread pool spun up for pure I/O; `async/await` wrapping CPU-intensive computation; "add more workers" as first response to any latency issue.
**When not**: When the concurrency model is dictated by the framework or runtime with no meaningful choice.
**See also**: [eng.P1]

## [eng.P7] Isolate, document, and protect optimizations
**Confidence**: high
**Severity**: major
**Context**: general
**Updated**: 2026-06-25
**Evidence**: Pragmatic Programmer; Google performance engineering
**Trigger**: A change trades code clarity for performance using bit manipulation, manual memory management, or other hard-to-read techniques.
**Directive**: Isolate behind a clear interface. Comment with: (1) the measured bottleneck, (2) the numbers that justified the trade-off, (3) a benchmark test that fails if the optimization regresses or becomes unnecessary.
**Because**: Uncommented optimizations become unmaintainable puzzles nobody dares touch or remove. (maintainability + efficiency)
**Smells**: Cryptic bit-manipulation with no comment; "optimized" paths with no benchmark; dead optimizations nobody removed.
**When not**: N/A — any optimization that sacrifices clarity requires documentation.
**See also**: [eng.P1]

## Internal relationships
[eng.P1] --supports--> [eng.P7]   algorithm fixes are easy to understand; micro-opts always need documentation
[eng.P3] --supports--> [eng.P2]   minimizing allocations also improves cache utilization
[eng.P4] --supports--> [eng.P5]   batching and lazy evaluation are complementary: reduce and defer I/O
[eng.P6] --supports--> [eng.P4]   async I/O enables batching without blocking
