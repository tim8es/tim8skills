# tim8skills

A collection of reusable agent skills. Most existing skills were created for [Claude Code](https://claude.com/claude-code); **Video Storycraft targets OpenAI Codex** and uses the standard `SKILL.md` format.

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
| [feed-pulse](feed-pulse/) | FeedPulse monitors RSS and Atom feeds for content research — blogs, news sites, newsletters, and other feed sources. Supports multiple feeds with categories, filters, summaries, and bounded feed content. |
| [video-storycraft](video-storycraft/) | Audience-first video ideas, hooks, scripts, voiceover, shot lists, production QA, and retention analysis — without additional runtime dependencies. |
| [windows-pwsh-agent-guardrails](windows-pwsh-agent-guardrails/) | Guardrails for Windows PowerShell usage by AI agents: wrappers, paths, approvals, CLI quirks, and command-failure handling. |

## Usage

Each skill uses a `SKILL.md` with YAML frontmatter; some legacy skills use Claude Code-specific workflows.

### Video Storycraft in Codex

This repository is a **skill catalog**, not itself a Codex installation directory. To use Video Storycraft across projects, copy `video-storycraft/` to `~/.agents/skills/video-storycraft/`. For a single project, put it in `<project>/.agents/skills/video-storycraft/`. Do **not** duplicate both installations unnecessarily.

After PR #2 is merged, Codex can also install it by invoking `$skill-installer` with `https://github.com/tim8es/tim8skills/tree/main/video-storycraft`.

Call `$video-storycraft` explicitly (for example, `$video-storycraft Напиши сценарий Shorts об AI-переводе EPUB`), or let Codex select it automatically based on the skill description. Restart Codex if the newly installed skill does not appear in `/skills`. No dependencies are required.

Documentation: [Build Skills for Codex](https://learn.chatgpt.com/docs/build-skills).

## License

[MIT](LICENSE)
