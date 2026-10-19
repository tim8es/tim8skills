# Dynamic Workflows for Obsidian Kanban — opt-in

## Design decision: reuse, do not clone Claude Code's runtime

Native Claude Code Dynamic Workflows (introduced May 28, 2026) execute a
JavaScript script with `agent()`, `parallel()`, `pipeline()`, `phase()`,
structured results, concurrency bounds, and checkpoint/replay. Their proprietary
runtime is not a Python library. **Do not reimplement these primitives in Kanban.**

Sources:
- Anthropic: https://claude.com/blog/introducing-dynamic-workflows-in-claude-code
- Claude Code docs: https://code.claude.com/docs/en/dynamic-workflows
- Standalone MIT re-host of the same DSL for Codex:
  https://github.com/scasella/claude-dynamic-workflows-codex
  (evaluated upstream commit `16524bea870a51ac7bfb3dc7dce77e333c7a56e1`,
  license MIT; install separately, NOT vendored or auto-downloaded).

The Kanban extension is strictly an **adapter + evidence gate + measurement
layer**. Native Claude Code should use native Dynamic Workflows when available.
The standalone path delegates all worker scheduling and execution to the re-host.

## Legacy compatibility

Default mode and all existing board columns remain unchanged. Opt in to
independent worker orchestration by adding `workflowMode: dynamic` to the
spec's YAML frontmatter (prefer the existing Kanban mutator once supported;
do not manually edit a live spec during simultaneous transitions). The new
completion gate runs ONLY for such tasks.

Kanban lifecycle: BACKLOG → TODO → IN PROGRESS → TESTING → IN REVIEW → DONE.
A workflow may have many worker phases and retries **within** one card.
Do not map every `agent()` call to a new Kanban card.

## Authoring the workflow

Use Claude Code's Workflow tool to author a JS workflow, or author one from the
same DSL for the standalone re-host. An example:

```javascript
export const meta = {
  name: "auth-review",
  description: "Independent verification of auth implementation",
  phases: [{title: "Inspect"}, {title: "Adversarial review"}]
};
phase("Inspect");
const audits = await parallel([
  () => agent("Audit auth API behavior and missing tests.", {label:"Backend"}),
  () => agent("Audit auth UI and accessibility.", {label:"Frontend"})
]);
phase("Adversarial review");
const verdicts = await pipeline(audits.filter(Boolean),
  async (finding) => agent(
    "Independently reproduce or refute this finding: " + JSON.stringify(finding),
    {label:"Verify"}
  )
);
return {approved: verdicts.every(Boolean), audits, verdicts};
```

This script illustrates syntax only. `every(Boolean)` is NOT a sufficient
acceptance test for production: use structured claims, reproduce findings,
and run objective tests before completing Kanban. The script must be inspected
for malicious or runaway behavior before running.

## Run via standalone Codex re-host

Prerequisites: Node >=18, authenticated `codex app-server`, downloaded and
reviewed `scasella/claude-dynamic-workflows-codex` runner at the pinned revision.
No third-party code is auto-executed by the skill.

Commands from project root (adjust skill path to detected SCRIPT_PREFIX):

```bash
python obsidian-kanban/scripts/kanban.py dynamic plan "." auth \
  --runner /trusted/claude-dynamic-workflows-codex/runner/bin/run-workflow.js \
  --workflow workflows/auth-review.workflow.js

python obsidian-kanban/scripts/kanban.py dynamic run "." auth \
  --runner /trusted/claude-dynamic-workflows-codex/runner/bin/run-workflow.js \
  --workflow workflows/auth-review.workflow.js \
  --approve-execution --budget 200000

python obsidian-kanban/scripts/kanban.py dynamic verify "." auth \
  --test-cmd "python -m unittest discover -s tests" \
  --artifact src/auth.py --artifact tests/test_auth.py

python obsidian-kanban/scripts/kanban.py dynamic status "." auth
```

`run` defaults to read-only worker sandbox. File edits require
`--workspace-write`, which also requires `--approve-execution`. The runner
executes untrusted agent code within configured Codex permissions; Node `vm`
alone is not a security boundary. Do not use `--workspace-write` on an
unreviewed script or an untrusted repo.

Independent `verify` executes the supplied test command separately from the
agents. It logs the exit code, elapsed time, truncated stdout/stderr, and SHA-256
of each supplied artifact. If an artifact changes, `DONE` is blocked.
Evidence is local operational data, **not cryptographic attestation**: agents
with access to this directory can tamper with it. Protect journal paths against
untrusted workers in a stronger deployment.

Native Claude Code work: use the same spec and native script, but currently
the bridge's automatic machine-readable journal applies only to the standalone
re-host. Do **not** bypass `DONE` gating for native runs; a future native
adapter must produce equivalent evidence.

## Reliability and limits

- `tasks/.dynamic-workflows/runs/<slug>.json` is a per-task latest-run journal;
  a new run invalidates earlier verification.
- `verify` records an artifact fingerprint and blocks a stale result.
- The underlying re-host implements parallel/pipeline, checkpoint/resume, model
  routing, and runner limits; use its own `--resume` for incomplete workers.
- The current bridge is synchronous and does not expose cancel/pause/attach;
  it is a first integration increment, not durable supervision.
- Existing `kanban.py resume` remains a Kanban context packet, not a process
  checkpoint. A process crash can require invoking upstream recovery manually.
- `workflowMode: dynamic` guards DONE via `hooks.before_move`.
- The exit code of `move_card.py` now signals failure for board/spec
  partial writes. Reconcile before retrying, because board may have moved.

## Proving quality and efficiency

First run **offline mechanism regression tests**, which prove safety invariants
but do NOT prove higher coding quality or token efficiency:

```bash
python -m unittest discover -s obsidian-kanban/scripts -p 'test_dynamic_workflow.py'
python -m unittest discover -s obsidian-kanban/scripts -p 'test_kanban.py'
```

Then perform paired **real end-to-end tasks**, alternating execution order,
using identical model/version, repository snapshot, task prompts, budgets,
and independent hidden acceptance tests. Store JSONL with one row per execution:

```json
{"task_id":"auth-001","repeat":0,"variant":"legacy","passed":false,"wall_seconds":400,"tokens":23000}
{"task_id":"auth-001","repeat":0,"variant":"dynamic","passed":true,"wall_seconds":310,"tokens":26000}
```

The rows above illustrate format **only** and must never be counted as results.
For actual measurements:

```bash
python obsidian-kanban/scripts/kanban.py dynamic-eval results.jsonl
```

Primary metrics: verified completion, wrong-DONE rate (must be zero),
wall-clock to verified output, tokens per verified task, manual interventions
and crash recovery. Reserve unseen tasks and report confidence intervals and
failures, not just the best run. The evaluator refuses unmatched run pairs,
and only marks quality + speed as confirmed if sample and CI gates pass.
Token efficiency is reported independently: it can worsen even when speed improves.

## Release phases

1. v0.1 (this branch): upstream runner bridge, manual approval, evidence gate,
   legacy compatibility, offline regression tests, paired evaluator.
2. v0.2: native Claude Code journal adapter, automatic upstream resume mapping,
   append-only audit history, guard runtime log against worker tampering.
3. v0.3: full paired E2E evaluation on unseen coding tasks, calibrated budgets,
   fault injection (SIGKILL, duplicated finish, disk-write error, changed inputs).
4. Promote to default **only if** measurements show gains without regressions.
