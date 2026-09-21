# Worked Examples

These examples demonstrate the review method. Reuse the reasoning pattern, not the conclusions mechanically.

## Example 1: Weekly product report

### Input

A team needs to collect data every Monday from three fixed sources, calculate known metrics, fill a fixed report template, and send it to Slack. The model should highlight important changes.

### Facts

- schedule is fixed;
- sources are fixed;
- metrics are known;
- report structure is fixed;
- language interpretation is useful for the summary.

### Decomposition

| Step | Type | Source of truth |
|---|---|---|
| schedule run | deterministic | scheduler |
| fetch source data | deterministic | source APIs |
| calculate metrics | deterministic | application code / query |
| detect missing source | deterministic | retrieval status |
| explain notable changes | language/reasoning | structured metrics |
| draft report text | language/reasoning | structured metrics |
| send report | action | delivery integration |

### Recommendation

Use a deterministic scheduled workflow with an LLM only for interpretation and wording.

An autonomous agent is unnecessary because the sources, order, and output are known before execution.

### What would change the recommendation

A constrained agent may become useful if the system must investigate anomalies by choosing among different tools and sources at runtime.

---

## Example 2: Product refund

### Input

A customer asks for a refund. The system must inspect the order and process the refund when allowed.

### Important distinction

Understanding the customer's request is a language problem. Refund eligibility and refund amount are business-policy and financial-data problems.

### Safer boundary

```text
customer message
→ LLM identifies intent/order
→ get_order
→ check_refund_eligibility
→ {eligible, reason, amount}
→ LLM explains result
→ create_refund_request
→ deterministic approval / human approval if required by policy
```

The model should not recreate the refund policy from prompt text if the backend can enforce it.

The model should not invent the amount.

### What would change the recommendation

If policy explicitly permits fully automatic refunds below a certain threshold, the backend may execute them directly after deterministic checks. That threshold must come from the real policy, not from the reviewer.

---

## Example 3: Fifty internal documents

### Input

A user asks whether to load all 50 internal documents into a long-context model or build RAG.

### Review

The document count alone is not enough to decide.

Relevant questions:
- total token volume;
- how often the documents change;
- whether each query needs most documents or only a subset;
- repeated query volume;
- citation requirements;
- access-control requirements;
- cost and latency constraints.

### Provisional recommendation

If the corpus is small, mostly relevant to each query, and changes rarely, direct long-context use may be simpler.

If queries repeatedly need small subsets of a growing corpus, or source-level permissions/citations matter, retrieval is more likely to be justified.

The recommendation is provisional until corpus size, query pattern, and freshness requirements are known.

---

## Example 4: Support investigation agent

### Input

Support receives varied technical incidents. Depending on the initial evidence, the system may need to inspect logs, query account state, search documentation, or ask the customer for more information.

### Review

The exact sequence cannot be fixed reliably before the investigation begins. Intermediate evidence changes the next step and tool selection.

### Recommendation

A constrained tool-using agent can be justified here, provided:
- tools are narrowly scoped;
- state-changing tools are separated from read-only investigation tools;
- the agent has explicit stop conditions;
- failed tools return structured errors;
- consequential actions require deterministic checks or human approval.

This is a case where runtime planning creates product value rather than merely adding complexity.
