# Windows Command Patterns

## OpenClaw CLI

Use the Windows command launcher `openclaw.cmd` on this machine. Avoid changing PowerShell execution policy merely to use the PowerShell shim. After OpenClaw configuration changes, run the documented configuration validator. Restart only with explicit authority.

## OpenClaw `exec`

Run ordinary executables directly and pass the Windows working directory through the tool field. Do not add a shell wrapper by habit.

## Interactive PowerShell instructions

PowerShell syntax belongs in examples explicitly intended for a PowerShell prompt. Distinguish those examples from OpenClaw `exec` input. Use the PowerShell call operator only where PowerShell itself is the execution surface and the executable path requires it.

## Node and Windows command wrappers

Known compatibility pattern for Node 24 when a `.cmd` or `.bat` launcher cannot be started directly:

- API: the synchronous or asynchronous Node process-launch API appropriate to the program;
- executable: the value of `process.env.ComSpec`;
- arguments: Command Processor disable-auto-run, preserve-quoting, execute-command switches, followed by the wrapper command;
- verification: propagate and inspect the child exit status.

Prefer the real executable or script beneath the wrapper when it is stable and documented. This pattern is described structurally rather than as executable code because Skill Workshop security scanning correctly treats embedded process-spawning code as sensitive.

## Paths and scratch files

Use exact absolute Windows paths outside the current workspace. Put scratch files needed by OpenClaw file tools under `.openclaw/tmp/<task>/`.

## Append-style files

Read the current content, append a compact dated block, and verify earlier entries remain intact. Replace the full file only on an explicit replacement request.
