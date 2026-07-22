---
name: "windows-pwsh-agent-guardrails"
description: "Guard Windows PowerShell, wrappers, paths, approvals, OpenClaw CLI, and command failures."
---

# Windows PowerShell Agent Guardrails

Use this skill for Windows command work involving PowerShell, `pwsh`, Windows PowerShell, `cmd.exe`, `.cmd`/`.bat`, OpenClaw CLI, Node process launching, paths, quoting, approvals, configuration, or a command failure on Windows.

Purpose: make Windows execution predictable and keep reusable Windows/Pwsh execution knowledge in this skill rather than long-term memory.

## Trigger model

Load this skill before acting when:

- a request needs runnable Windows instructions;
- Windows CLI execution, wrappers, launchers, configuration, services, or schedulers are involved;
- a command fails at the shell, runtime, wrapper, path, quoting, encoding, or permission layer;
- OpenClaw CLI behavior on Windows is involved;
- a reusable Windows/Pwsh lesson may need recording.

Load only the matching reference:

- `references/error-taxonomy.md` for diagnosis;
- `references/command-patterns.md` for runnable instructions and launchers;
- `references/anti-patterns.md` for instruction review;
- `references/windows-pwsh-gotchas.md` for confirmed recurring failures.

## Execution preflight

Before running or recommending a command:

1. Identify the execution surface: OpenClaw tool, direct executable, PowerShell, command wrapper, Node launcher, or target program.
2. Prefer a first-class OpenClaw tool over shell execution.
3. When `exec` is appropriate, prefer direct executable invocation.
4. Use exact Windows paths; use absolute paths outside the workspace.
5. Keep scratch files needed by file tools under `.openclaw/tmp/` inside the workspace.
6. Quote only the path or argument that requires quoting.
7. Preserve safety boundaries:
   - never execute `/approve` through a shell or tool;
   - inspect existing state before changing configuration, services, schedulers, shell startup files, or exposure;
   - validate configuration after changes;
   - restart Gateway only when explicitly authorized by the current request.

## Command decision tree

Use this order unless a tool contract requires otherwise:

1. First-class OpenClaw tool.
2. Direct executable via `exec`.
3. Project or package launcher when it is the real interface.
4. Command Processor mediation only when confirmed wrapper or shell-built-in semantics require it.
5. PowerShell only when PowerShell language features are required.
6. WSL only when explicitly requested or when the project is explicitly WSL-based.

## Failure triage loop

1. Preserve the exact command and error.
2. Classify the layer using `references/error-taxonomy.md`.
3. Try one minimal correction for that layer rather than several speculative variants.
4. Verify with an exit code, tool output, file inspection, status command, test, or screenshot.
5. If the correction is reusable, update this skill through `skill_workshop`; do not move it to `MEMORY.md` unless it is independently a durable user preference or safety constraint.

## Knowledge capture policy

Add a lesson only when it is confirmed by live behavior or authoritative documentation, likely to recur, and concerns Windows execution, shell semantics, wrappers, paths, approvals, or OpenClaw CLI behavior.

Do not add secrets, session identifiers, raw transcripts, transient provider failures, unverified guesses, generic preferences, project business facts, or duplicates.

Store confirmed gotchas in `references/windows-pwsh-gotchas.md` using: symptom, layer, anti-pattern, correct pattern, and verification.

## Output expectation

Report the verified result or exact blocker. For a command correction, include the corrected pattern and evidence. Keep routine explanations concise.
