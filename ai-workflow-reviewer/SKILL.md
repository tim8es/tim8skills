---
name: ai-workflow-reviewer
description: Reviews proposed AI and LLM workflows for product and business use cases. Use when the user wants to decide whether a task should use deterministic code, an LLM, RAG, a tool-using agent, or human approval; review an existing AI architecture; identify unsafe model responsibilities; define tool boundaries, sources of truth, failure handling, and validation criteria. Do not present recommendations as facts when requirements are missing or assumed.
---

# AI Workflow Reviewer

Review AI-enabled workflows using a fixed architecture framework. The goal is not to maximize AI usage. The goal is to find the simplest architecture that satisfies the stated requirements with clear control over data, actions, and failure modes.

## Core principle

Prefer the least autonomous solution that solves the problem:

```text
deterministic code
→ deterministic workflow + LLM
→ retrieval + LLM
→ constrained tool-using agent
→ autonomous agent
```

Move to the right only when a stated requirement creates a concrete need for additional model reasoning or runtime autonomy.

## Mandatory review workflow

Do not recommend an architecture before completing these steps.

### 1. Extract facts

List only requirements explicitly present in the user's description.

Examples:
- sources are fixed;
- report runs weekly;
- refund amount comes from an order system;
- output format is fixed.

Do not mix inferred requirements into this section.

### 2. Separate assumptions

List anything required for the analysis but not stated by the user.

Examples:
- an API is available;
- sending a report does not require approval;
- the knowledge base changes frequently.

If an assumption materially affects the recommendation, say so.

### 3. Decompose the workflow

Break the process into meaningful operations. For each operation classify its primary nature as one of:

- `deterministic` — fixed rules, calculations, validation, scheduling, routing, state transitions;
- `language/reasoning` — interpretation, summarization, classification, explanation, synthesis;
- `retrieval` — locating authoritative external or internal information;
- `action` — changes external state or creates side effects;
- `human judgment` — policy, approval, accountability, or ambiguity that should remain with a person.

A step may have more than one classification. State the dominant one and any important secondary property.

### 4. Identify sources of truth

For every important fact or value, identify where it should come from.

Examples:
- refund eligibility → policy service;
- payment amount → billing system;
- KPI values → analytics query;
- document content → retrieved source;
- final wording → LLM.

The model must not become the source of truth for values that can be obtained or computed deterministically.

### 5. Check autonomy requirements

Evaluate whether runtime planning is actually needed.

A tool-using agent is justified only when at least one important part of the workflow cannot be fixed in advance, for example:
- the next step depends on intermediate findings;
- the required tool cannot be selected before execution;
- the system must investigate an open-ended problem;
- the relevant source set is dynamic and must be discovered;
- the number or order of steps varies meaningfully by case.

Multiple steps alone do not justify an agent.

### 6. Check retrieval requirements

Do not recommend RAG solely because documents exist.

Consider retrieval when:
- relevant information is larger than practical prompt context;
- information changes independently of the application;
- answers require source selection from a larger corpus;
- citations or traceability matter;
- repeated queries should not resend the whole corpus;
- access control or document-level filtering matters.

A large context window and RAG are not interchangeable architectural choices. Compare them against the actual workload.

### 7. Check actions and risk

Identify actions with side effects and classify them as:
- reversible / low impact;
- consequential but recoverable;
- irreversible, financial, legal, security-sensitive, or externally visible.

For consequential actions, prefer:
- deterministic validation before execution;
- idempotent tool contracts where relevant;
- explicit tool responses as the source of truth;
- approval or confirmation when accountability should remain human.

Do not place critical business rules solely in prompts when they can be enforced by application code or backend services.

### 8. Compare architecture candidates

Consider only candidates that plausibly fit the requirements. Usually compare two or three of:

- deterministic workflow;
- workflow + LLM;
- retrieval + LLM;
- constrained agent;
- agent + human approval.

Compare them using:
- determinism;
- required autonomy;
- observability;
- failure recovery;
- implementation complexity;
- hallucination surface;
- source-of-truth clarity;
- human oversight.

Do not add an agent candidate merely for symmetry.

### 9. Recommend the simplest sufficient architecture

The recommendation must be derived from the previous analysis, not from general enthusiasm for AI.

Explain:
- why this architecture is sufficient;
- which responsibilities remain deterministic;
- where the LLM adds value;
- which responsibilities the LLM must not own.

### 10. State uncertainty and reversal conditions

Always include:
- assumptions;
- unresolved risks;
- what must be validated before implementation;
- what new requirement would change the recommendation.

## Decision rules

Use these as guardrails, not as substitutes for analysis.

- Fixed schedule + fixed sources + fixed sequence usually indicates a deterministic workflow.
- Natural-language transformation alone usually needs an LLM, not an agent.
- Known tools in a known order usually indicate workflow orchestration, not agent planning.
- Dynamic investigation can justify a constrained agent.
- Business rules, monetary values, permissions, eligibility, and irreversible state changes should come from deterministic systems or explicit human decisions.
- Retrieval should provide evidence; generation should not fabricate missing evidence.
- A tool failure is not equivalent to a valid empty result.
- If the model cannot distinguish missing data from zero, redesign the tool contract.

## Required output

Use the structure in [references/output-contract.md](references/output-contract.md).

The final recommendation must clearly distinguish:
1. facts;
2. assumptions;
3. derived conclusions;
4. recommendation.

Never hide an assumption inside the recommendation.

## Reference routing

Read only what is needed for the current task:

- architecture decisions and agent/RAG criteria: [references/decision-framework.md](references/decision-framework.md)
- required review output and self-check: [references/output-contract.md](references/output-contract.md)
- worked examples: [references/examples.md](references/examples.md)

## Anti-patterns

Do not:
- recommend an autonomous agent because a task has several steps;
- use the LLM to calculate authoritative business metrics when code can do it;
- let the LLM decide policy eligibility when a policy service can enforce it;
- treat a long context window as automatic replacement for retrieval;
- treat RAG as mandatory for every document-based task;
- invent APIs, approvals, policies, sources, SLAs, or business rules;
- describe a missing requirement as if it were known;
- hide tool failures behind a polished model-generated answer;
- optimize for architectural sophistication over reliability.
