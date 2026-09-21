# Decision Framework

Use this reference when the review requires a choice between deterministic automation, LLM generation, retrieval, or agent autonomy.

## 1. Determine where uncertainty exists

Not every form of uncertainty requires an LLM.

| Uncertainty | Preferred handling |
|---|---|
| Exact calculation | deterministic code |
| Fixed validation rule | deterministic code |
| Natural-language interpretation | LLM |
| Semantic classification with fuzzy boundaries | LLM, with evaluation |
| Finding relevant material in a corpus | retrieval |
| Choosing next step from intermediate findings | constrained agent |
| Policy or accountability decision | deterministic policy and/or human |
| Irreversible external action | deterministic guardrail + approval where appropriate |

## 2. Deterministic workflow vs agent

Prefer a deterministic workflow when most of the following are true:
- the sequence of steps is known before execution;
- the same tools are used every run;
- inputs and outputs have stable schemas;
- retries and failures can be handled with normal program logic;
- autonomy does not improve the user outcome.

Consider a constrained agent when one or more are materially true:
- intermediate findings determine which tool to call next;
- the workflow branches in ways that cannot be enumerated reasonably;
- the agent must investigate an open-ended question;
- the source or tool set must be discovered at runtime;
- planning itself is part of the product value.

Do not confuse branching logic with agentic planning. A normal `if/else` decision based on structured fields remains deterministic.

## 3. LLM placement

Good LLM responsibilities:
- summarize;
- classify ambiguous language;
- extract structured information from unstructured text;
- explain;
- synthesize evidence;
- generate drafts;
- rank or cluster semantically when approximate behavior is acceptable.

Poor LLM responsibilities when deterministic alternatives exist:
- arithmetic;
- date-window enforcement;
- identity and authorization;
- financial amount calculation;
- eligibility rules;
- exact state transitions;
- deduplication keys;
- idempotency;
- permission checks.

## 4. Source-of-truth test

For each important output value ask:

1. Is this value factual or generated?
2. Does an authoritative system already own it?
3. Can it be computed deterministically?
4. What happens if the model is wrong?
5. Can the user trace the value to evidence?

If an authoritative system exists, the LLM should consume its output rather than recreate the logic.

## 5. RAG vs long context

Use long context directly when:
- the corpus is small enough to send comfortably;
- most or all documents are relevant every time;
- the corpus is relatively static;
- setup simplicity matters more than repeated-query efficiency;
- access control does not require document-level retrieval filtering.

Consider RAG when:
- only a subset of a larger corpus is relevant to each query;
- the corpus changes frequently;
- repeated queries would repeatedly resend large volumes of text;
- source traceability matters;
- document-level permissions matter;
- latency or cost improve by retrieving only relevant chunks.

RAG introduces its own failure modes:
- poor chunking;
- missed retrieval;
- stale indexes;
- embedding mismatch;
- ranking errors;
- incomplete source coverage.

A RAG system must therefore be evaluated as retrieval + generation, not just generation.

## 6. Tool contract test

A reliable tool response should distinguish at least:
- success;
- valid empty result;
- partial result;
- error.

When relevant, include:
- stable identifiers;
- authoritative values;
- machine-readable status;
- explicit error reason;
- provenance or source link;
- idempotency support for state-changing operations.

The LLM should not infer these fields from prose when the backend can provide them directly.

## 7. Human-in-the-loop test

Human approval is more justified when:
- the action is irreversible;
- money moves;
- legal or compliance consequences exist;
- the model is resolving a genuinely ambiguous policy case;
- the user expects accountability from a named person;
- the cost of a false positive is materially higher than delay.

Human approval is less useful when it merely rubber-stamps a deterministic, low-risk operation.

## 8. Recommendation discipline

A recommendation is valid only if it can be stated as:

```text
Because the requirements show X,
and Y does not require model autonomy,
use Z.

This would change if requirement Q became true.
```

If the conclusion cannot be tied back to stated facts or explicit assumptions, the analysis is incomplete.
