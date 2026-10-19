# Dynamic Workflow — architecture and runtime contract (opt-in)

> For the full installation, first run, and benchmark commands, start with
> [QUICKSTART-DYNAMIC.md](../QUICKSTART-DYNAMIC.md).

## Reused implementation (not a new orchestrator)

- Official [Claude Code Dynamic Workflows](https://code.claude.com/docs/en/workflows):
  native JavaScript scripts, agent(), parallel(), pipeline(), phase(),
  checkpoints and resumption. The native runtime stays inside Claude Code.
- [Unofficial standalone Codex re-host](https://github.com/scasella/claude-dynamic-workflows-codex):
  preserves the same workflow DSL, binds agent() to Codex app-server,
  implements parallel scheduling, per-agent journal replay, model/sandbox
  controls, and native-looking progress viewers. Reviewed, MIT-licensed
  revision: **16524bea870a51ac7bfb3dc7dce77e333c7a56e1**.

Kanban does NOT reimplement the agent scheduler or DSL; it owns task state,
quality transitions and independent acceptance evidence. The runner remains
an explicit external dependency, not copied or downloaded by the skill.

## Layer boundary

| Component | Responsibilities | Source files |
|---|---|---|
| Kanban control plane | Card/status/DoD, permissions, human UAT | SKILL.md, hooks.py, move_card.py |
| Workflow template | Read-only parallel inspect → serial implement → parallel adversarial reviews → bounded repair | templates/dynamic-implementation.workflow.js |
| Upstream runner | agent(), parallel(), pipeline(), checkpoint/replay, Codex model calls | External upstream repo |
| Kanban bridge | Arguments, opt-in approval, runner lifecycle, journal path, retries delegated to upstream | scripts/dynamic_workflow.py |
| Evidence gate | Independent command results, script/input/output hashes | scripts/dynamic_gate.py |
| Task setup | Extract DoD and objective task from spec, do not overwrite reviewed scripts | scripts/dynamic_prepare.py |
| Evals | Isolated Git worktrees, same baseline SHA/model/hidden tests, token reports, paired CI | scripts/dynamic_benchmark.py, dynamic_eval.py |

The existing state machine is unchanged:

BACKLOG → TODO → IN PROGRESS → TESTING → IN REVIEW → DONE

Upstream stages live **inside** one Kanban task. Do not generate a separate
board card for each agent call. Dynamic mode is activated only by the
`workflowMode: dynamic` field (added by `dynamic init`). Legacy tasks follow
the old subagent-runner flow.

## Real entrypoints

All commands use the existing dispatcher:

```text
kanban.py dynamic doctor <workspace> <slug> --runner <path>
kanban.py dynamic init <workspace> <slug> [--overwrite]
kanban.py dynamic plan <workspace> <slug> --runner <path>
kanban.py dynamic run <workspace> <slug> --runner <path>
  --workspace-write --approve-execution [--frontier|--model ...]
kanban.py dynamic resume <workspace> <slug> --runner <path>
  --workspace-write --approve-execution
kanban.py dynamic import-native <workspace> <slug> --result-file <json>
  --approve-execution
kanban.py dynamic verify <workspace> <slug> --test-cmd <command>
  --artifact <path> [--artifact <path> ...]
kanban.py dynamic status <workspace> <slug>
kanban.py dynamic-benchmark <manifest> --runner <path> --model <model>
  [--execute] [--repeat N]
kanban.py dynamic-eval <results.jsonl>
```

## Workflow assurance

Before a dynamic card reaches DONE, **inside the transition hook**:

1. A completed upstream/native-import result explicitly says `approved: true`.
   Process exit 0 alone is insufficient.
2. The reviewed workflow script bytes still match their run-time SHA-256.
3. Generated task input bytes still match their run-time SHA-256 (if present).
4. A separate test process finished exit 0. A worker's self-attested PASS is
   not counted as a test.
5. At least one named output artifact still matches its SHA-256 recorded
   after the tests.
6. Existing Kanban review and lifecycle gates also apply.

Records are stored under `tasks/.dynamic-workflows/`:

```text
scripts/<slug>.workflow.js  # reviewed script, generated from template
inputs/<slug>.json          # task / acceptance criteria
upstream/<slug>.jsonl       # actual agent journal (the upstream runtime)
runs/<slug>.json            # latest run + independent verification
locks/<slug>.lock           # prevents simultaneous runs for one task
```

A new run uses upstream `--fresh` and invalidates any earlier verification
**before** execution. `resume` uses `--resume` against exactly the same
journal, script/inputs hash and sandbox policy. Incomplete processes leave
state `running`, which rejects DONE until replay succeeds and verification
is rerun. Manual Kanban `resume` is still a context packet, not a runner
restart.

The generated script's read-only inspection/review is parallel, whereas
writes are intentionally serialized. It chooses **at most one repair round**,
which limits uncontrolled cost and concurrent edit conflicts. The runtime
supports more advanced patterns, but tasks should only use more agents when
the measured gain justifies it.

## Native Claude Code distinction

Claude Code already provides background runs, `/workflows` and the
`ultracode` trigger. Use them directly when using Claude models. Its native
workflow process is not exposed as a portable Python API. For now,
`import-native` can ingest an explicitly saved native return JSON, followed
by an independent `verify`. This is an **external declaration**: without an
authenticated runtime receipt it does not prove provenance. Do not claim the
native CLI was automatically orchestrated by the Kanban bridge.

## Security and consistency boundaries

- `--approve-execution` is required to launch or import.
- `--workspace-write` must be intentionally selected; default is read-only.
- No `danger-full-access` mode is exposed by the bridge.
- Treat user-generated JS and task text as untrusted. A project may be
  malicious and have tool-side injection attempts.
- An agent with write access to the entire project may also alter the
  `tasks/.dynamic-workflows` journal; local hashes protect staleness but
  are not tamper-proof. Keep evidence in a protected external store for
  security-critical production use.
- `move_card.py` returns failure for board-only/spec-only divergence; a
  retried move refuses to claim success until reconciliation.
- The generated template is **not** a secure container. Enforce platform
  sandbox permissions and worktrees for untrusted tasks.
- The Codex bridge is synchronous: leave the terminal open while the runner
  executes. After a crash, invoke `resume` to replay cached completed agents;
  non-idempotent external side effects still require human assessment.

## Verification and honest success criterion

GitHub Actions checks `test_kanban.py` (legacy), `test_dynamic_workflow.py`
(integration/fault injection), a REAL upstream `--plan` run on the bundled
script, and a no-model upstream `run/resume/verify` smoke. Passing these only
proves mechanism compatibility, not higher real-world model quality.

`dynamic-benchmark` drives actual Codex CLI runs on separate detached Git
worktrees (single-agent legacy Kanban vs same-model dynamic workflow).
It needs model login and explicit `--execute`. It writes raw evidence files,
real token usage where measurable and acceptance results. `dynamic-eval`
reports per-task clustered confidence intervals, rejecting incomplete paired
records or absent resource measurements. A confirmed increase in quality/
efficiency requires adequate unseen tasks and positive, robust comparisons.
Until then the claim is **not proven**.
