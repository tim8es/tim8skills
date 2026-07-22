# Windows Command Error Taxonomy

Classify a failure before changing the command.

## OpenClaw tool contract

Signals: schema rejection, unsupported parameter, workspace boundary, host mismatch, or approval state before the target program ran.

Response: follow the tool contract; do not bypass a first-class tool with shell execution.

## Windows shell or runtime

Signals: parser errors, executable not recognized, WindowsApps alias failure, shell-dependent behavior, or PowerShell execution-policy rejection.

Response: prefer direct executable invocation; use the working Windows launcher; require PowerShell only for PowerShell language features.

## Wrapper or launcher

Signals: `.cmd`/`.bat`, package shim, or Node process-launch API fails before the target program starts.

Response: use Command Processor mediation only when wrapper semantics require it; otherwise invoke the underlying executable or script directly.

## Path, quoting, or encoding

Signals: wrong working directory, unexpected argument splitting, spaces or Cyrillic path problems, or output created in the wrong location.

Response: use exact Windows paths, set the working directory explicitly, and quote only the affected argument.

## Permissions or approval

Signals: approval pending, access denied, execution-policy rejection, elevation requirement, or a protected security/configuration boundary.

Response: use the native approval flow, show the exact command when approval is requested, and do not loosen policy as a shortcut.

## Target program

Signals: the program starts and then emits its own validation, build, test, or configuration error.

Response: diagnose the target program rather than changing shells.

## External or transient service

Signals: network timeout, rate limit, provider preflight, remote authentication, or service outage.

Response: separate scheduler, execution, delivery, and provider layers; respect retry guidance; do not call a forced manual run a root-cause fix.
