# Windows/Pwsh Gotchas

Store only confirmed reusable Windows, PowerShell, wrapper, path, approval, and OpenClaw CLI failures. Exclude secrets, session identifiers, raw transcripts, guesses, and one-off noise.

## Prefer the Windows OpenClaw launcher

- Symptom: the PowerShell shim is blocked by execution policy.
- Layer: Windows shell or runtime.
- Anti-pattern: weakening execution policy to reach OpenClaw CLI.
- Correct pattern: use `openclaw.cmd` on this machine.
- Verification: the command reaches OpenClaw rather than the PowerShell policy gate.

## WindowsApps PowerShell alias error 1312

- Symptom: the WindowsApps `pwsh.exe` alias fails with error 1312.
- Layer: Windows shell or runtime.
- Anti-pattern: retrying the alias or treating the result as a target-program failure.
- Correct pattern: avoid a PowerShell wrapper when possible; otherwise use a known working installed shell path.
- Verification: the intended target starts without the alias error.

## Node 24 and Windows command wrappers

- Symptom: a Node process-launch API returns `EINVAL` for a `.cmd` or `.bat` launcher.
- Layer: wrapper or launcher.
- Anti-pattern: diagnosing the target program before confirming that it started.
- Correct pattern: use `process.env.ComSpec` mediation with separate Command Processor switches and command arguments, or invoke the underlying executable/script directly.
- Verification: the target starts and its real exit status is available.

## Workspace-readable scratch files

- Symptom: a later file tool cannot access scratch output.
- Layer: OpenClaw tool contract and path.
- Anti-pattern: creating scratch files outside the workspace or under an invented Unix temporary path.
- Correct pattern: use `.openclaw/tmp/` inside the workspace when file tools need later access.
- Verification: the file tool reads or edits the output.

## Append-style files

- Symptom: earlier journal or log content is overwritten.
- Layer: file lifecycle.
- Anti-pattern: full-file replacement without reading current content.
- Correct pattern: read before appending and preserve earlier entries.
- Verification: prior entries remain intact.

## Capture template

- Title and date.
- Symptom or exact minimal error.
- Classified layer.
- Anti-pattern.
- Correct pattern.
- Verification evidence.
