# DRS:HA Fork Orientation

Этот каталог описывает локальную структуру проекта в:

```bash
/Users/dmitry/Desktop/DRS:HA_fork
```

Внутри сейчас два отдельных git-репозитория:

```text
DRS:HA_fork/
├── masakari/   # custom HA recovery, staged recovery, Redfish fencing, admin API
└── watcher/    # Watcher backend API hardening and specs for Watcher Horizon UI
```

## Git repositories

`watcher/` has an upstream `origin` remote pointing to OpenDev:

```text
origin  https://opendev.org/openstack/watcher.git
```

The GitHub repository for this Watcher work is:

```text
https://github.com/lebtmalorny-rgb/Watcher.git
```

Recommended local remote setup is to keep `origin` as upstream and add GitHub
as a separate writable remote:

```bash
cd '/Users/dmitry/Desktop/DRS:HA_fork/watcher'
git remote add github https://github.com/lebtmalorny-rgb/Watcher.git
git push -u github master
```

If you prefer GitHub to be the default push target, change only the push URL:

```bash
git remote set-url --push origin https://github.com/lebtmalorny-rgb/Watcher.git
```

## Главное правило по консоли

Запускать команды разработки лучше не из верхнего каталога
`/Users/dmitry/Desktop/DRS:HA_fork`, а из конкретного репозитория:

```bash
cd '/Users/dmitry/Desktop/DRS:HA_fork/masakari'
```

или:

```bash
cd '/Users/dmitry/Desktop/DRS:HA_fork/watcher'
```

Верхний каталог удобен только для навигации, сравнения двух направлений и
хранения общих заметок. `git`, `tox`, `stestr`, поиск по коду и правки лучше
выполнять внутри `masakari/` или `watcher/`, потому что у них разные `.git`,
`tox.ini`, зависимости, тесты и ветки.

## Когда работать в `masakari/`

Использовать эту директорию для всего, что относится к custom Masakari HA:

- staged recovery через etcd;
- эвакуация VM в stopped state и последующий staged start;
- лимит одновременного старта VM на destination host;
- Redfish fencing перед recovery;
- Masakari Admin REST API;
- runtime admin config для `staged_recovery.max_parallel_starts_per_host`;
- Masakari Horizon/Admin API requirements;
- тесты Masakari API, engine, TaskFlow, nova helper, etcd state.

Рабочая директория:

```bash
cd '/Users/dmitry/Desktop/DRS:HA_fork/masakari'
```

Полезные документы:

```text
docs/specs/CODEX_MASAKARI_STAGED_RECOVERY_ETCD.md
docs/specs/CODEX_MASAKARI_STAGED_RECOVERY_ETCD_IMPLEMENTATION.md
docs/specs/CODEX_MASAKARI_REDFISH_FENCING_ETCD.md
docs/specs/CODEX_MASAKARI_FENCING_OPERATIONS.md
docs/specs/CODEX_MASAKARI_HORIZON_ADMIN_API_REQUIREMENTS.md
docs/specs/CODEX_MASAKARI_ADMIN_CONFIG_API_IMPLEMENTATION.md
docs/specs/CODEX_MASAKARI_STAGED_RECOVERY_EXAMPLES_AND_TUNING.md
```

Частые зоны кода:

```text
masakari/api/openstack/ha/                 # HA API extensions
masakari/api/openstack/ha/schemas/         # API request schemas
masakari/ha/api.py                         # HA service/API layer
masakari/compute/nova.py                   # Nova integration
masakari/engine/drivers/taskflow/          # recovery workflow tasks
masakari/conf/                             # oslo.config options
masakari/policies/                         # oslo.policy rules
masakari/tests/unit/api/openstack/ha/      # API tests
masakari/tests/unit/engine/                # engine/taskflow tests
masakari/tests/unit/compute/               # Nova helper tests
```

Пример точечного запуска тестов:

```bash
stestr run masakari.tests.unit.api.openstack.ha.test_admin_config.AdminConfigTestCase
```

Более широкий запуск:

```bash
tox -e py3
tox -e pep8
```

## Когда работать в `watcher/`

Использовать эту директорию для Watcher backend/API и спецификаций для
отдельного Watcher Horizon plugin:

- audit list filters, pagination, sorting;
- audit/action plan API behavior;
- audit create/update regression coverage;
- data model endpoint behavior;
- services, scoring engines, strategy state endpoints;
- API reference and release notes for Watcher;
- client-facing requirements for a future standalone Horizon plugin.

Рабочая директория:

```bash
cd '/Users/dmitry/Desktop/DRS:HA_fork/watcher'
```

Полезные документы:

```text
docs/specs/codex_task_watcher_backend_api.md
docs/specs/codex_task_watcher_horizon_plugin.md
docs/specs/CODEX_WATCHER_HORIZON_BACKEND_IMPLEMENTATION.md
docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md
docs/WATCHER_EPOXY_2025_1_ANALYSIS.md
```

Частые зоны кода:

```text
watcher/api/controllers/v1/        # REST API controllers
watcher/objects/                   # versioned objects
watcher/db/sqlalchemy/             # DB API and models
watcher/decision_engine/           # strategies, planner, model
watcher/applier/                   # action execution
watcher/tests/api/v1/              # API tests on Epoxy / stable/2025.1
api-ref/source/                    # API reference
releasenotes/notes/                # release notes
```

Пример точечного запуска тестов:

```bash
tox -e py3 -- watcher.tests.api.v1.test_audits
```

Более широкий запуск:

```bash
tox -e py3
tox -e pep8
```

### Локальное тестовое окружение для этого workspace

В текущем macOS workspace системный `python3` указывает на Python 3.14, а
Watcher Epoxy рассчитан на Python 3.10-3.12. Для проверок был установлен
локальный Python 3.12:

```text
/Users/dmitry/Desktop/DRS:HA_fork/watcher/.uv-python/
/Users/dmitry/Desktop/DRS:HA_fork/watcher/.venv/
```

Из-за двоеточия в пути `DRS:HA_fork` часть Python packaging tooling и tox
некорректно разбирают путь проекта. Для запуска тестов используется временная
копия без двоеточия:

```text
/private/tmp/watcher-src-no-colon
/private/tmp/watcher-venv-py312
/private/tmp/watcher-python-install
```

Чтобы повторить точечные тесты после правок, сначала синхронизировать рабочую
копию:

```bash
cd '/Users/dmitry/Desktop/DRS:HA_fork/watcher'
rsync -a --exclude .git --exclude .venv --exclude .tox --exclude .uv-cache --exclude __pycache__ . /private/tmp/watcher-src-no-colon/
rsync -a .git /private/tmp/watcher-src-no-colon/
```

Затем запускать `stestr` из временной копии:

```bash
cd /private/tmp/watcher-src-no-colon
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 \
  /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.api.v1.test_audits.TestListAudit
```

## Как не смешивать Masakari и Watcher

Masakari и Watcher здесь связаны общей темой HA/операторского UI, но это разные
слои:

- Masakari отвечает за host failure recovery, fencing, evacuation, staged start.
- Watcher отвечает за optimization/audit/action plan API и data model.
- Horizon plugin должен быть отдельным потребителем API, а не местом для
бизнес-логики recovery или optimization.

Если задача про отказ compute host, fencing, evacuation, leases, staged state
или лимит стартов VM, работать в `masakari/`.

Если задача про audits, audit templates, action plans, strategies, goals,
Watcher data model или `openstack optimize ...`, работать в `watcher/`.

Если задача про UI в Horizon, сначала определить, для какого backend:

- Masakari UI/API admin plugin: опираться на specs из `masakari/docs/specs`.
- Watcher UI/plugin: опираться на specs из `watcher/docs/specs`.

Сам Horizon plugin лучше держать отдельным репозиторием рядом с этими двумя, а
не внутри `masakari/` или `watcher/`, если только задача явно не говорит иначе.

## Рекомендуемая схема терминалов

Для работы по двум направлениям удобно держать два терминала:

```bash
# Terminal 1: Masakari
cd '/Users/dmitry/Desktop/DRS:HA_fork/masakari'
git status --short
```

```bash
# Terminal 2: Watcher
cd '/Users/dmitry/Desktop/DRS:HA_fork/watcher'
git status --short
```

Для обзора обоих репозиториев можно открыть третий терминал:

```bash
cd '/Users/dmitry/Desktop/DRS:HA_fork'
find . -maxdepth 2 -type d | sort
```

Но из этого верхнего каталога не стоит запускать `tox`, `stestr` или `git`
операции, если команда не указывает явно `-C masakari` или `-C watcher`.

## Быстрый старт перед новой задачей

1. Определить домен задачи: Masakari recovery или Watcher optimization.
2. Перейти в соответствующий репозиторий.
3. Проверить ветку и текущие изменения:

```bash
git branch --show-current
git status --short
```

4. Открыть ближайшую спецификацию из `docs/specs`.
5. Перед правками найти существующий тестовый модуль рядом с изменяемым кодом.
6. После правок запускать сначала точечные тесты, затем более широкий `tox`.

## Текущая локальная картина

На момент составления ориентира:

```text
masakari branch: staged-recovery-etcd
watcher branch:  stable/2025.1
watcher upstream remote: https://opendev.org/openstack/watcher.git
watcher GitHub repo:     https://github.com/lebtmalorny-rgb/Watcher.git
```

В `watcher` есть неотслеживаемые `docs/` и `.serena/`.
В `masakari` виден измененный `.DS_Store`; это служебный файл macOS, его лучше
не учитывать как часть разработки.
