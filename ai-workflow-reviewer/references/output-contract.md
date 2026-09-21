# Output Contract

Use this structure for every substantive review.

## 1. Problem framing

One short paragraph describing the user outcome and the system boundary.

## 2. Facts

List only facts explicitly provided by the user or by authoritative tool output.

## 3. Assumptions

List assumptions needed for the analysis. Mark assumptions that materially affect the recommendation.

If there are no material assumptions, say so.

## 4. Workflow decomposition

Use a table:

| Step | Primary type | Source of truth | Main risk |
|---|---|---|---|
| ... | deterministic / language / retrieval / action / human | ... | ... |

Keep the table focused on architecture-relevant steps.

## 5. Architecture candidates

Compare only plausible candidates.

For each candidate state:
- what remains deterministic;
- what the LLM does;
- whether runtime autonomy is required;
- main failure modes;
- operational complexity.

## 6. Recommendation

State one primary architecture when evidence is sufficient.

The recommendation must include:
- why it is sufficient;
- why a more autonomous design is unnecessary or justified;
- boundaries of model responsibility.

If evidence is insufficient, give a provisional recommendation and name the missing evidence.

## 7. Guardrails and failure handling

Include only controls relevant to the case.

Typical examples:
- tool responses are authoritative;
- missing data is distinct from zero;
- failed source is distinct from empty source;
- model cannot mutate configuration unless requested;
- high-impact action requires validation or approval;
- remote content is untrusted input.

## 8. Validate before implementation

List the smallest set of unknowns that should be checked before building.

Examples:
- API availability;
- source freshness;
- request volume;
- latency;
- evaluation dataset;
- cost constraints;
- permissions;
- failure/retry behavior.

## 9. What would change the recommendation

Name concrete requirement changes that would justify a different architecture.

Examples:
- sources become dynamic;
- sequence can no longer be known in advance;
- investigation requires runtime tool selection;
- policy changes require document retrieval;
- actions become financially consequential.

## Self-check before answering

Verify all of the following:

- Facts and assumptions are separate.
- No API, rule, policy, SLA, source, or approval flow was invented.
- Every LLM responsibility benefits from language or reasoning.
- Every deterministic responsibility has not been unnecessarily delegated to the model.
- Agent autonomy is tied to a concrete runtime need.
- Critical values have an explicit source of truth.
- Tool failure is not presented as a valid empty result.
- High-impact actions have suitable controls.
- The recommendation names conditions under which it would change.
- The answer does not claim certainty beyond the available evidence.
