# Session Commands — obsidian-kanban

> The user usually works in natural language. Slash commands are an alternative format for quick invocation.

| Command                                | Action                                                        |
| --------------------------------------- | -------------------------------------------------------------- |
| `/kanban`, `/tasks`                    | Activation + onboarding + summary                              |
| `/board <project>`                     | Show board state in chat                                        |
| `/status`                              | Summary across all projects                                    |
| `/new epic <name>`                     | Create an epic, start decomposition                             |
| `/new task <name> [--epic <slug>]`     | Create a task                                                   |
| `/take <slug>`                         | Take a task into work (TODO → IN PROGRESS)                      |
| `/test <slug>`                         | Move card to TESTING (IN PROGRESS → TESTING)                    |
| `/review <slug>`                       | Move card to IN REVIEW (TESTING → IN REVIEW)                    |
| `/done <slug>`                         | Move card to DONE (only from IN REVIEW)                         |
| `/block <slug> <reason>`               | Block a task                                                    |
| `/unblock <slug>`                      | Remove a blocker                                                |
| `/freeze <slug> <reason>`              | Move to ICEBOX                                                  |
| `/decompose <epic-slug>`               | Decompose an epic                                               |
| `/move <slug> <COLUMN>`                | Move a card via `<SCRIPT_PREFIX>/kanban.py move`                |
| `/remove <slug>`                       | Remove a card from the board via `remove-card`                  |
| `/next`                                | Show the next task by priority (REWORK→TODO→BACKLOG) via `next` |
| `/lint`                                | Run `<SCRIPT_PREFIX>/kanban.py lint` and show the report         |
| `/sync`                                | Run `<SCRIPT_PREFIX>/kanban.py sync "." --all` (or `--slug <slug>`) — property normalization; without `--all`/`--slug` the command fails |
| `/launch-agents [--epic <slug>] [--task <slug>]` | `--epic` (or no flag) — a subagent per active epic; `--task <slug>` — a subagent for a single task (§13) |
