# Dynamic Workflow для Kanban — готово к первому пользовательскому тесту

## Что изменилось

Реализация **не заменяет** твой Kanban и **не пишет собственный движок**.
В её основе — оригинальный JavaScript DSL Claude Code Dynamic Workflows и
[standalone Codex runner](https://github.com/scasella/claude-dynamic-workflows-codex)
(независимый MIT-проект, зафиксированная версия
`16524bea870a51ac7bfb3dc7dce77e333c7a56e1`).

Обычный Kanban остаётся неизменным. Для конкретной задачи можно включить
`workflowMode: dynamic`. Тогда применяется следующий сценарий:

1. Два независимых агента параллельно исследуют код **только на чтение**.
2. Один агент реализует изменение (параллельных редакторов нет).
3. Два новых агента проверяют решение независимо друг от друга.
4. При обнаружении ошибок запускается **не более одного** цикла исправления
   с повторной проверкой.
5. Отдельная команда запускает настоящие тесты проекта, сохраняет exit code
   и хеши артефактов.
6. Kanban запрещает переход в DONE, если подтверждение устарело или отсутствует.

Это не «магическая гарантия качества»: работающий код подтверждают
объективные тесты и сравнение с исходным вариантом.

## Первый запуск (Codex)

**Предусловия:** Python 3.10+, Node 18+, установленный и авторизованный
`codex`. Нужно работать в репозитории с существующей доской Kanban и
карточкой со спецификацией и DoD. Ниже `auth-google` — пример slug.

Установи отдельно проверенную версию runner:

```bash
git clone https://github.com/scasella/claude-dynamic-workflows-codex.git ../claude-dynamic-workflows-codex
git -C ../claude-dynamic-workflows-codex checkout 16524bea870a51ac7bfb3dc7dce77e333c7a56e1
codex login
```

В корне проекта, где установлен `obsidian-kanban`:

```bash
# Создать сценарий и входные данные из готовой спеки.
python obsidian-kanban/scripts/kanban.py dynamic init . auth-google

# Проверить окружение.
python obsidian-kanban/scripts/kanban.py dynamic doctor . auth-google --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js

# Посмотреть реальный план upstream БЕЗ обращения к моделям.
python obsidian-kanban/scripts/kanban.py dynamic plan . auth-google --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js
```

Открой и проверь `tasks/.dynamic-workflows/scripts/auth-google.workflow.js`
и `tasks/.dynamic-workflows/inputs/auth-google.json`.

Когда сам решишь запустить выполнение с правом редактирования:

```bash
python obsidian-kanban/scripts/kanban.py dynamic run . auth-google --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js --frontier --budget 2000000 --timeout 7200 --workspace-write --approve-execution
```

Если процесс прервался, вместо нового `run` используй `resume` с
**теми же аргументами**:

```bash
python obsidian-kanban/scripts/kanban.py dynamic resume . auth-google --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js --frontier --budget 2000000 --timeout 7200 --workspace-write --approve-execution
```

После выполнения — обязательная независимая проверка. **Замени пути и
команду на реальные тесты твоего проекта**:

```bash
python obsidian-kanban/scripts/kanban.py dynamic verify . auth-google --test-cmd "python -m unittest discover -s tests" --artifact src/auth.py --artifact tests/test_auth.py
python obsidian-kanban/scripts/kanban.py dynamic status . auth-google
```

После подтверждения качества агент завершает прежний цикл Kanban:
`TESTING → IN REVIEW → DONE`. Переходы и DoD нельзя пропускать.

Если skill установлен в `.agents/skills/obsidian-kanban/`, замени
`obsidian-kanban/scripts/` на фактический `SCRIPT_PREFIX`.

## Claude Code без Codex

У Claude Code есть собственные Dynamic Workflows: `ultracode` или прямой
запрос «создай и запусти dynamic workflow». Используй JS-сценарий как
основу. После нативного запуска сохрани итоговый JSON c
`{"approved":true}`, импортируй его через `dynamic import-native` и
выполни отдельное `dynamic verify`. Импорт файла не равен
проверенной аттестации от Claude — это честно отражено в архитектуре.

## Доказательство качества и эффективности

```bash
# Сначала показывает план: 0 запусков модели, 0 токенов.
python obsidian-kanban/scripts/kanban.py dynamic-benchmark obsidian-kanban/evals/manifest.example.json --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js --model YOUR_EXACT_MODEL

# Только после настройки реальных кейсов и проверок — добавить --execute:
python obsidian-kanban/scripts/kanban.py dynamic-benchmark obsidian-kanban/evals/manifest.example.json --runner ../claude-dynamic-workflows-codex/runner/bin/run-workflow.js --model YOUR_EXACT_MODEL --repeat 2 --execute

python obsidian-kanban/scripts/kanban.py dynamic-eval kanban-eval-output/results.jsonl
```

Внутри — независимые Git worktree с одним SHA, одинаковые критерии
приёмки и модель, JSONL-следы, длительность и токены. Для убедительного
вывода нужны десятки **различных** задач и независимые тесты.
Одного примера из `manifest.example.json` недостаточно.

**Текущий статус проверки:** GitHub Actions успешно проходит исходные
тесты Kanban, новые unit/integration/fault-injection тесты, настоящий
`--plan` у upstream, а также его безмодельные `run/resume/verify`.
Реальные модели на полноценных A/B-кейсах здесь пока не запускались,
поэтому **рост качества и эффективности ещё не доказан**.

Подробная архитектура и ограничения:
[references/dynamic-workflow.md](references/dynamic-workflow.md).
Англоязычный пошаговый runbook:
[QUICKSTART-DYNAMIC.md](QUICKSTART-DYNAMIC.md).
