# Windows/Pwsh Anti-Patterns

## Shell wrapping by habit

Do not put ordinary executable calls behind Command Processor, PowerShell command mode, the PowerShell call operator, or WSL without a confirmed reason.

## Mixing execution surfaces

Do not copy an interactive PowerShell expression into OpenClaw `exec` without checking whether the target executable should be invoked directly.

## Unix path leakage

Do not create scratch data under Unix-style temporary paths and then expect workspace-only file tools to access it. Use `.openclaw/tmp/` inside the workspace.

## Approval bypass

Never execute `/approve` through shell, browser automation, or messaging. Use the native approval flow and preserve the exact command requiring approval.

## Configuration clobbering

Do not replace configuration wholesale, change network/security boundaries, or restart Gateway as a diagnostic shortcut. Inspect, minimally patch, validate, then restart only with authority.

## Append-only overwrite

Do not overwrite journals, daily notes, or learning logs before reading them. Preserve prior entries.

## Memory pollution

Do not add routine Windows command failures to `MEMORY.md`. Persist only confirmed reusable execution gotchas in this skill through Skill Workshop.
