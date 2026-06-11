# Реализация backend-доработок Watcher для Horizon plugin

Этот документ фиксирует, что реализовано в fork-е Watcher поверх
`stable/2025.1` / OpenStack Epoxy 2025.1 для будущей интеграции с отдельным
Horizon Watcher plugin.

Документ написан как краткий implementation summary в стиле соседнего
репозитория Masakari: он описывает фактическое состояние backend-контракта,
модель данных, API и границы совместимости. Это не план работ по Horizon UI.

## Контекст

Репозиторий:

```text
/Users/dmitry/Desktop/DRS:HA_fork/watcher
```

Рабочая ветка:

```text
feature/audit-state-filter-2025.1
```

Базовая ветка:

```text
stable/2025.1
```

Целевой релиз:

```text
OpenStack Epoxy / 2025.1
```

GitHub repository:

```text
https://github.com/lebtmalorny-rgb/Watcher.git
```

## Цель доработок

Цель backend-ветки - подготовить Watcher API к корректной работе отдельного
Horizon Watcher plugin без client-side hacks и без изменения существующих
ответов API.

Основные задачи:

1. Дать Horizon возможность фильтровать audits на стороне backend.
2. Сохранить обратную совместимость публичных API response bodies.
3. Зафиксировать существующие OSC/API сценарии regression-тестами.
4. Документировать изменения модели данных и API для будущей интеграции.

## Что реализовано

### Audit state filter

Добавлена поддержка server-side фильтра `state`:

```http
GET /v1/audits?state=<STATE>
GET /v1/audits/detail?state=<STATE>
```

Допустимые значения берутся из существующих Watcher audit state constants:

```text
PENDING
ONGOING
SUCCEEDED
FAILED
CANCELLED
SUSPENDED
DELETED
```

Поведение:

- фильтр применяется до pagination;
- invalid state возвращает `400 Bad Request`;
- compact list поддерживает комбинации `goal`, `strategy`, `state`;
- detail list поддерживает `state`, но не получает новый `strategy` filter;
- active filters сохраняются в `next` pagination links.

Схема БД для этого не менялась: используется существующая колонка
`audits.state`.

### Audit template UUID filter

Добавлена поддержка server-side фильтра `audit_template_uuid`:

```http
GET /v1/audits?audit_template_uuid=<UUID>
GET /v1/audits/detail?audit_template_uuid=<UUID>
```

Для этого добавлена persisted-связь между audit и audit template:

```text
audits.audit_template_id -> audit_templates.id ON DELETE SET NULL
```

Поведение:

- при `POST /v1/audits` с `audit_template_uuid` backend сохраняет внутренний
  `audit_template_id`;
- фильтр возвращает только audits, у которых сохранена эта связь;
- historical audits не backfill-ятся;
- audits, созданные напрямую от `goal`, не попадают под этот фильтр;
- если audit template удален hard-delete/purge, audit сохраняется, а
  `audit_template_id` очищается;
- после очистки `audit_template_id` такой audit больше не матчится
  `audit_template_uuid` фильтром.

Важно для совместимости: в API `1.0` - `1.5` публичный audit response body
не расширен. Начиная с API `1.6` в audit response body появляется публичное
поле `audit_template_uuid`; внутренний numeric `audit_template_id` по-прежнему
не раскрывается.

Дополнительный P1 hardening:

- зафиксировано поведение `audit_template_uuid + sort_key + sort_dir`;
- unknown `audit_template_uuid` возвращает пустой список;
- invalid UUID format для `audit_template_uuid` возвращает `400 Bad Request`;
- эти проверки не меняют API, а только закрепляют существующий контракт.

### Audit template UUID response field

Начиная с API microversion `1.6` audit responses содержат публичное поле:

```json
{
  "audit_template_uuid": "2e93db2c-29d7-4314-9cb8-fbc99bc1d5e7"
}
```

Где появляется поле:

```http
GET /v1/audits
GET /v1/audits/detail
GET /v1/audits/<AUDIT_UUID>
POST /v1/audits
```

Поведение:

- для audit, созданного через audit template, возвращается UUID template;
- для audit, созданного напрямую от `goal`, возвращается `null`;
- после hard-delete/purge template возвращается `null`;
- `audit_template_id` остается internal-only и не появляется в REST response;
- list/detail строят mapping `audit_template_id -> uuid` для текущей страницы,
  а не делают отдельный lookup на каждую строку.

### Audit create contract

Добавлена и усилена regression coverage для сценариев создания audit, которые
нужны UI:

- `ONESHOT` audit create;
- `CONTINUOUS` audit create с top-level `interval`;
- cron-style interval;
- отсутствие `interval` для `CONTINUOUS`;
- запрет `interval` для `ONESHOT`;
- `EVENT` audit create без webhook execution;
- `auto_trigger` для continuous audits;
- `start_time` и `end_time` в рамках существующего microversion behavior;
- `force` для non-continuous audit create;
- `force=True` для `CONTINUOUS` возвращает `400 Bad Request`;
- strategy `parameters` проверяются по существующей strategy schema.

Новых request/response полей для audit create не добавлялось.

### Action plan API contract

Зафиксировано и усилено поведение action plan API, которое потребуется Horizon:

```http
GET /v1/action_plans?audit_uuid=<AUDIT_UUID>&strategy=<STRATEGY>
```

Что важно:

- используется backend parameter `audit_uuid`, не `audit`;
- combined filters `audit_uuid` и `strategy` коррелированы к одной строке
  action plan;
- `next` pagination links сохраняют active filters;
- для API `1.0` - `1.4` cancel action plan остается PATCH-based state
  transition;
- начиная с API `1.5` добавлен dedicated endpoint:

```http
POST /v1/action_plans/<ACTION_PLAN_UUID>/cancel
OpenStack-API-Version: infra-optim 1.5
```

- endpoint использует те же state transitions:

```text
RECOMMENDED -> CANCELLED
PENDING     -> CANCELLED
ONGOING     -> CANCELLING
```

- при cancel actions, принадлежащие этому action plan, переходят в
  `CANCELLED`, unrelated actions не затрагиваются.

Для `ONGOING -> CANCELLING` immediate перевод actions в `CANCELLED` не
выполняется: дальнейшая остановка остается частью существующего applier flow.

### Data model API contract

Зафиксировано текущее backend-поведение:

```http
GET /v1/data_model
GET /v1/data_model?data_model_type=compute
GET /v1/data_model?data_model_type=compute&audit_uuid=<AUDIT_UUID>
GET /v1/data_model?data_model_type=compute&detail=true
```

Контракт для Horizon:

- default `data_model_type` уже равен `compute`;
- parameter называется `data_model_type`, не `type`;
- `audit_uuid` передается в Decision Engine API;
- invalid `data_model_type` возвращает `404 Not Found`;
- начиная с API `1.7` поддержан query parameter `detail`;
- `detail` недоступен до API `1.7` и возвращает `406 Not Acceptable`;
- `detail=true`, `detail=True`, `detail=1` трактуются как `True`;
- `detail=false`, `detail=False`, `detail=0` трактуются как `False`;
- invalid boolean value, например `detail=yes`, возвращает
  `400 Bad Request`;
- при `detail=false` или без параметра response остается прежним:
  `context` содержит compact list из `available_data_model.to_list()`;
- при `detail=true` response меняется только для microversion `1.7`:
  `context` содержит XML string из `available_data_model.to_string()`.

Важно для Horizon plugin: `detail=true` не вводит новую JSON-схему Common Data
Model. Это raw XML-представление текущей модели. UI может показывать его как
подробный/raw view или парсить XML на своей стороне, но не должен ожидать
JSON object/array detail schema от backend.

Если OSC в конкретном окружении timeout-ится без type, это нужно проверять на
стороне watcherclient/OSC path, а не менять REST contract без отдельного
основания.

### Services, scoring engines, strategy state

Дополнительно зафиксированы backend-контракты, нужные UI:

- services list/detail, pagination, sort-key и policy behavior уже покрыты
  существующими тестами;
- scoring engines list/detail поддерживают `marker`, `limit`, `sort_key`,
  `sort_dir`;
- strategy state endpoint уже существует:

```http
GET /v1/strategies/<strategy>/state
```

Для scoring engines и strategy state добавлены/усилены regression-тесты.

## Изменения модели данных

Добавлена nullable-колонка:

```text
audits.audit_template_id
```

Связь:

```text
audits.audit_template_id -> audit_templates.id ON DELETE SET NULL
```

Файлы:

```text
watcher/db/sqlalchemy/models.py
watcher/db/sqlalchemy/alembic/versions/c2f4b8d6e3a1_add_audit_template_id_to_audits.py
watcher/objects/audit.py
watcher/db/sqlalchemy/api.py
```

Object model:

- `objects.Audit.VERSION` поднят до `1.8`;
- добавлено nullable поле `audit_template_id`;
- object fingerprint обновлен в tests.

Upgrade behavior:

- existing audits не backfill-ятся;
- после миграции новые template-backed audits получают `audit_template_id`;
- hard-delete/purge audit template не удаляет audits;
- backend явно очищает `audits.audit_template_id` при
  `destroy_audit_template()`, чтобы поведение не зависело только от FK
  enforcement конкретной БД;
- DB FK также задан с `ON DELETE SET NULL`.

## Public API compatibility

Сохранены важные границы совместимости:

- для API `1.0` - `1.5` не добавлены новые поля в audit list/detail/create
  response body;
- в API `1.6` добавлено только публичное поле `audit_template_uuid`;
- numeric `audit_template_id` остается internal/provenance field;
- не добавлен `strategy` query parameter в `GET /v1/audits/detail`;
- существующие `goal`, `strategy`, `limit`, `marker`, `sort_key`, `sort_dir`
  behavior сохранены;
- action plan cancel через PATCH сохранен для совместимости;
- dedicated action plan cancel endpoint добавлен только в microversion `1.5`.
- data model `detail` добавлен только в microversion `1.7`; default
  `GET /v1/data_model` и compact response не изменены.

Публичные расширения API по microversions `1.5` - `1.7` описаны в отдельном
P2 design document:

```text
docs/specs/CODEX_WATCHER_P2_API_EXTENSIONS.md
```

## Контракт для Horizon plugin

Рекомендуемые capability flags:

```python
WATCHER_BACKEND_SUPPORTS_AUDIT_STATE_FILTER = True
WATCHER_BACKEND_SUPPORTS_AUDIT_TEMPLATE_FILTER = True
WATCHER_BACKEND_EXPOSES_AUDIT_TEMPLATE_UUID = True  # API >= 1.6
WATCHER_BACKEND_SUPPORTS_DATA_MODEL_DETAIL = True  # API >= 1.7
```

Horizon plugin должен:

- использовать server-side `state` filter для audit list views;
- отправлять Watcher audit states в uppercase;
- использовать server-side `audit_template_uuid` filter только когда включен
  capability flag;
- читать `audit_template_uuid` из audit response body только при API `>= 1.6`;
- не пытаться читать `audit_template_id` из audit response body;
- отправлять `detail=true` в data model API только при API `>= 1.7`;
- обрабатывать `data_model.context` как XML string при `detail=true`;
- следовать backend-provided `next` links, не пересобирать pagination URLs;
- использовать `audit_uuid`, не `audit`, для action plan filtering;
- не отправлять `force=True` для `CONTINUOUS` audits;
- отправлять `interval` как top-level field, не внутри `parameters`;
- валидировать `parameters` как JSON object до вызова backend;
- использовать `data_model_type=compute` для data model view по умолчанию.

## Документация и release notes

Обновлены:

```text
api-ref/source/parameters.yaml
api-ref/source/watcher-api-v1-audits.inc
api-ref/source/watcher-api-v1-datamodel.inc
docs/WATCHER_EPOXY_2025_1_ANALYSIS.md
docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md
releasenotes/notes/audit-state-query-filter-2ad0c3df0af66f13.yaml
releasenotes/notes/action-plan-filter-pagination-b4e12a2c2ad0c9df.yaml
releasenotes/notes/audit-template-filter-4f65d2cb0dfd13f2.yaml
releasenotes/notes/action-plan-dedicated-cancel-endpoint-3f7c9a8b1d2e4f60.yaml
releasenotes/notes/audit-template-uuid-response-6a1f9c2e4d8b7a30.yaml
releasenotes/notes/data-model-detail-api-7d2e4a1f9c0b6e53.yaml
```

Основной подробный API contract для будущего Horizon plugin:

```text
docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md
```

Анализ upstream/master/stable branches и фактического Epoxy layout:

```text
docs/WATCHER_EPOXY_2025_1_ANALYSIS.md
```

## Основные backend commits

Серия изменений поверх `stable/2025.1`:

```text
21f04b58 Fix combined audit goal and strategy filters
a28531ce Harden audit create validation coverage
2f20b1e2 Return bad request for invalid audit intervals
2034a12c Preserve action plan filters in pagination
52dd3379 Cover audit rename patch API
8ef8d3a1 Cover data model API query contract
ddf4886d Cover action plan cancel action states
7eb1b59a Cover scoring and strategy API contracts
2ee12af6 Document audit template filter design
406f3efc Plan audit template filter implementation
a24602fe Add audit template DB filter tests
8dfe57fb Add audit template relationship to audits
6515cdaf Add audit template API regression tests
0b92c8c8 Add audit template filter API support
f8f0599b Document audit template audit filter
a29550f3 Preserve audits when purging audit templates
5f7bbb56 Harden audit template delete references
```

## Проверки

Для этого workspace тесты запускались из colon-free mirror:

```text
/private/tmp/watcher-src-no-colon
```

С virtualenv:

```text
/private/tmp/watcher-venv-py312
```

Ключевые проверки, которые проходили на ветке:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 \
PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run \
watcher.tests.db.test_audit watcher.tests.db.test_audit_template \
watcher.tests.api.v1.test_audits
```

Результат для audit DB/API slice после audit-template реализации:

```text
215 tests passed
```

После hardening `destroy_audit_template()` дополнительно запускался slice:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 \
PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run \
watcher.tests.db.test_audit_template watcher.tests.api.v1.test_audits \
watcher.tests.db.test_purge
```

Результат:

```text
187 tests passed
```

После P1 hardening audit-template фильтра запускался полный audit API slice:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 \
PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run \
watcher.tests.api.v1.test_audits
```

Результат:

```text
150 tests passed
```

Также проходили:

```bash
git diff --check
python -m py_compile <changed python files>
sphinx-build -W --keep-going -b html api-ref/source api-ref/build/html
sphinx-build -E -W --keep-going -b html -j auto releasenotes/source releasenotes/build/html
```

## Что не входит в эту backend-ветку

Не реализовывалось:

- Horizon plugin UI;
- integration tests с реальным OpenStack deployment;
- изменения в Horizon, watcher-dashboard или python-watcherclient;
- webhook trigger UI или webhook execution;
- изменение audit response schema;
- backfill historical audits;
- client-side filtering behavior.

## Следующий этап, когда плагин будет в работе

Когда начнется работа над Horizon plugin, этот backend contract можно считать
готовым для Phase 1 plugin work:

1. API wrapper.
2. Capability flags.
3. Cursor pagination через backend `next` links.
4. Audit list filters `goal`, `strategy`, `state`, `audit_template_uuid`.
5. Create Audit form с корректной обработкой `interval`, `force`,
   `auto_trigger`, `EVENT`, `start_time`, `end_time`, `parameters`.

Пока plugin и integration tests не трогаются.
