# tim8skills

A collection of [Claude Code](https://claude.com/claude-code) skills — packaged instructions and scripts that extend Claude Code for specific workflows: code review, task management, process consulting, RSS monitoring, health data analysis, and Windows PowerShell safety.

## Skills

| Skill | Description |
|---|---|
| [agent-mind](agent-mind/) | A focused software engineering reviewer. Writes, reviews, and refactors code guided by a maintained graph of engineering directives covering naming, code design, readability, maintainability, architecture, performance, security, and systems patterns. |
| [apple-health-reader](apple-health-reader/) | Parses and analyzes Apple Health export data (HealthKit XML export) into daily aggregates (steps, heart rate, sleep, calories, weight) stored in a local JSON database with a Markdown report. |
| [github-releases](github-releases/) | Discovers published GitHub releases, compares versions, retrieves bounded notes, and supplies release checks for host-managed monitoring. |
| [memory-wiki-router](memory-wiki-router/) | Routes incoming knowledge into the right memory wiki layer, page type, and safety flow. |
| [obsidian-kanban](obsidian-kanban/) | Manages AI development tasks via an Obsidian Kanban board: creating tasks/epics, decomposition (epic → task → subtask), metadata tracking, status updates, and role-aware execution. Activated via `/kanban`, `/tasks`, `/board`. |
| [ok-process-observability](ok-process-observability/) | Process-cost observability for AI agent work sessions: captures live workflow incidents, runs a post-run session self-audit, and reports deterministic context-cost metrics over the kanban task workspace. |
| [process-manager-suite](process-manager-suite/) | Specialized workflows for process management in consulting: AS-IS/TO-BE process mapping, process audits, KPI/governance design, and SOP drafting. |
| [rss-reader](rss-reader/) | Monitors RSS and Atom feeds for content research — blogs, news sites, newsletters, and any feed source. Supports multiple feeds with categories, filters, and summaries. |
| [windows-pwsh-agent-guardrails](windows-pwsh-agent-guardrails/) | Guardrails for Windows PowerShell usage by AI agents: wrappers, paths, approvals, CLI quirks, and command-failure handling. |

## Usage

Each skill directory follows the [Claude Code skill format](https://docs.claude.com/en/docs/claude-code/skills): a `SKILL.md` with YAML frontmatter (`name`, `description`) plus optional `references/`, `scripts/`, `templates/`, and `agents/` subdirectories. Copy a skill directory into your Claude Code skills folder to use it.

## License

[MIT](LICENSE)
