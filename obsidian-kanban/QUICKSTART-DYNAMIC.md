# Dynamic Workflow — ready-to-try quickstart

This is an opt-in integration. The **real orchestration engine** is Claude
Code Dynamic Workflows or an independently installed Codex re-host of the
same JavaScript DSL. Kanban keeps task lifecycle, DoD, approval gates, and
evidence. The default Kanban behavior is unchanged.

## 0. Requirements

- Python >=3.10 and Node.js >=18.
- For Codex: authenticated `codex` CLI (`codex login`).
- A local repository that already has a `tasks/<board>.md` and a task spec at
  `tasks/specs/<slug>.md` with an explicit DoD checklist.
- A separate checkout of the MIT-licensed upstream runner:

```bash
git clone https://github.com/scasella/claude-dynamic-workflows-codex.git ../claude-dynamic-workflows-codex
git -C ../claude-dynamic-workflows-codex checkout 16524bea870a51ac7bfb3dc7dce77e333c7a56e1
codex login
```

Install only from the reviewed URL. This checkout is **not installed,
downloaded or executed by the Kanban skill itself**. Review the generated
JavaScript before granting permission to run agents.

In a user project the `kanban.py` path depends on where the skill is
installed. Use the detected `SCRIPT_PREFIX` from ONBOARDING.md.

## 1. Prepare an EXISTING card

Set `SLUG` to a real Kanban task slug, e.g. `auth-google`.
In this example `obsidian-kanban/scripts` is the skill's real relative path.

```bash
python obsidian-kanban/scripts/kanban.py dynamic init . auth-google
```

This creates:

- `tasks/.dynamic-workflows/scripts/auth-google.workflow.js`: a
  **reviewable** JS script with parallel read-only investigation, one
  writer, parallel independent reviews and bounded repair.
- `tasks/.dynamic-workflows/inputs/auth-google.json`: task from your spec
  and DoD. Changes to this file invalidate previously verified completion.
- `workflowMode: dynamic` in the spec YAML (and only this mode requires
  the additional DONE gate).

It **does not launch agents**. Re-running `init` never overwrites an edited
workflow; use `--overwrite` deliberately to regenerate from the canonical
template.

## 2. Configure the runner and dry-run the script

```bash
python obsidian-kanban/scripts/kanban.py dynamic doctor . auth-google \
  --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js

python obsidian-kanban/scripts/kanban.py dynamic plan . auth-google \
  --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js
```

`plan` executes the upstream runner with `--plan`, **no model calls**.
Check the agent count and proposed token budget. Dynamic fan-outs over
model-generated lists are a lower bound; the bundled script uses a fixed fan-out.

## 3. Start the work (Codex implementation mode)

```bash
python obsidian-kanban/scripts/kanban.py dynamic run . auth-google \
  --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js \
  --frontier --budget 2000000 --timeout 7200 \
  --workspace-write --approve-execution
```

`--workspace-write` is required to implement code; omit it to perform only
a read-only inspection (the template intentionally returns `approved:false`
if no implementation was permitted). Parallel inspection and review agents
always have `sandbox:read-only`. The template permits at most one writer at
a time. Review files before allowing the write sandbox.

The upstream runner persists agent-level replay state in
`tasks/.dynamic-workflows/upstream/<slug>.jsonl`; the bridge persists
the latest Kanban outcome in `tasks/.dynamic-workflows/runs/<slug>.json`.

After an interruption, **do not use `run` again** (it is intentionally fresh):

```bash
python obsidian-kanban/scripts/kanban.py dynamic resume . auth-google \
  --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js \
  --frontier --budget 2000000 --timeout 7200 \
  --workspace-write --approve-execution
```

Resume rejects changed task input, changed JS script, and changed sandbox
permissions; these require a new run instead.

## 4. Verify independently and complete the Kanban lifecycle

Select a real test command and all relevant output file paths for your task:

```bash
python obsidian-kanban/scripts/kanban.py dynamic verify . auth-google \
  --test-cmd "python -m unittest discover -s tests" \
  --artifact src/auth.py --artifact tests/test_auth.py

python obsidian-kanban/scripts/kanban.py dynamic status . auth-google
```

Replace the examples with **tests appropriate to your repository**. A
successful subprocess plus checked checkboxes is not proof that behavior is
correct: prefer independent, pre-established tests and an adversarial review.

After reviewer sign-off, use the existing `kanban.py check` and `move`
commands through the ordinary Kanban roles. DONE is rejected until all
dynamic evidence is current. This bridge does **not** bypass state-machine
transitions, write checkboxes on your behalf or automatically move the card
from BACKLOG to DONE.

If you are working through an AI coding agent, tell it:

> Use the installed obsidian-kanban skill on this task in dynamic mode.
> Run init/plan, show the reviewed JS and budget, ask only for permission
> before actual execution, then run or resume, perform independent tests,
> complete the normal Kanban roles and report status/evidence. Never waive
> the DONE gate.

## Native Claude Code (without the Codex runner)

Native Claude Code Dynamic Workflows is available using the `ultracode`
keyword or a direct request to create a workflow. Use the reviewed JS and
task input as source material. Claude's native Workflow tool executes its own
agent calls and shows `/workflows`; this Python bridge does NOT attempt to
call the private native runtime.

Ask Claude to save the final workflow return object to a JSON file in your
project; it must explicitly contain `{"approved":true}` for a successful
run, and supply that file:

```bash
python obsidian-kanban/scripts/kanban.py dynamic import-native . auth-google \
  --workflow tasks/.dynamic-workflows/scripts/auth-google.workflow.js \
  --result-file reports/claude-workflow-result.json --approve-execution
```

Then execute `verify` exactly as above. Native import records a
user-supplied result; it is **not a cryptographic attestation** of the native
runtime and must never be presented as independently proven provenance.

## 5. Measurement, not marketing

The feature branch runs legacy regression tests and upstream integration
smoke tests. Those do **not** show improved output quality.

To evaluate real agents, prepare `evals/manifest.json` from the documented
example and run the isolated paired benchmark. The benchmark **does not spend
tokens until `--execute` is supplied**:

```bash
python obsidian-kanban/scripts/kanban.py dynamic-benchmark \
  obsidian-kanban/evals/manifest.example.json \
  --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js \
  --model YOUR_MODEL_NAME

# REAL agents / token usage. Read the plan and costs before adding --execute.
python obsidian-kanban/scripts/kanban.py dynamic-benchmark \
  obsidian-kanban/evals/manifest.example.json \
  --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js \
  --model YOUR_MODEL_NAME --execute --repeat 2

python obsidian-kanban/scripts/kanban.py dynamic-eval \
  kanban-eval-output/results.jsonl
```

Each arm starts from the exact same detached Git commit in a separate
worktree, runs the same task, and is checked with the same independent
acceptance command. Logs and output SHA hashes are retained. A/B scheduling
order is randomized reproducibly. This compares *one Codex agent following the
legacy Kanban skill* against the *Claude-style multi-agent workflow on Codex*.

**Important:** the Codex CLI baseline does not enforce exactly the same
token budget as the dynamic runner; use observed token totals when comparing
efficiency. The evaluator refuses unknown token counts and does not declare
higher quality based on small or non-comparable samples.

Use at least ~20 different unseen coding tasks, 30+ matched pairs,
independent hidden acceptance tests, and review representative failures.
If required metrics are unavailable, the correct output is **inconclusive**.

## Known limits

- Claude's **native** workflow engine is a separate process with its own
  progress/control UI; a native run is not launched through this Python CLI.
- The standalone bridge executes in the current terminal (not a daemon) and
  needs a host process to keep it alive; resuming after interruption is manual.
- Journal files in the project can be modified by an actor with write access.
  Hashes prevent accidental staleness, **not malicious tampering**. For
  adversarial workloads, keep the evidence store and acceptance tests outside
  the workers' writable scope.
- A side-effectful agent call might run twice if the process fails after
  executing but before checkpoint; use idempotent actions and isolated worktrees.
- `doctor` checks binaries but does not guarantee your Codex account is logged in;
  `codex login` and an actual agent call are required for that.
