# P2 API extensions для Watcher Horizon integration

Документ описывает следующий слой backend-доработок после уже реализованного
P0/P1 в ветке `feature/audit-state-filter-2025.1`.

Цель P2 - добавить публичные API-возможности, которые удобны для Horizon
Watcher plugin, но не ломают существующий Watcher API Epoxy / 2025.1.
Все изменения ниже должны идти через новые microversions. Поведение API
версий `1.0` - `1.4` остается без изменений.

## Границы совместимости

Обязательные правила для P2:

- не менять response body для существующих microversions;
- не раскрывать внутренний numeric `audit_template_id` через REST API;
- не менять семантику существующего `PATCH /v1/action_plans/<uuid>`;
- не менять default behavior `GET /v1/data_model`;
- не backfill-ить historical audits автоматически в runtime;
- каждое новое поле или endpoint покрывать negative/compatibility tests.

Текущий максимум API версии:

```text
1.4 - webhook trigger API
```

Планируемые P2 microversions:

```text
1.5 - dedicated cancel endpoint для action plans
1.6 - audit_template_uuid в audit response body
1.7 - detail flag для GET /v1/data_model
```

## P2.1: Dedicated cancel endpoint для action plans

Статус реализации: реализовано в backend API microversion `1.5`.

### Новый endpoint

```http
POST /v1/action_plans/<action_plan_uuid>/cancel
OpenStack-API-Version: infra-optim 1.5
```

Зачем нужен endpoint:

- Horizon получает явную команду `cancel`, а не должен собирать JSON Patch;
- UI-код становится симметричен существующему `start` endpoint;
- старый PATCH-based cancel остается совместимым и не удаляется.

### State transition contract

Endpoint должен использовать тот же state machine contract, который уже
разрешен через `PATCH /v1/action_plans/<uuid>`:

```text
RECOMMENDED -> CANCELLED
PENDING     -> CANCELLED
ONGOING     -> CANCELLING
```

Для остальных состояний endpoint возвращает ошибку в стиле существующих
invalid action plan transitions.

Immediate cancel behavior:

- если итоговое состояние `CANCELLED`, все actions этого action plan
  переводятся в `CANCELLED`;
- unrelated actions не затрагиваются;
- если итоговое состояние `CANCELLING`, дальнейшая остановка выполняется
  существующим applier flow.

### Policy

Рекомендуем добавить отдельное policy rule:

```text
action_plan:cancel
```

Причина: Horizon сможет отдельно включать/выключать операцию cancel, не
расширяя права на общий update. Если нужна минимальная правка, допустимо
временно переиспользовать `action_plan:update`, но в целевом P2 контракте
лучше иметь отдельное правило.

### Response

Response body должен совпадать с обычным `ActionPlan` representation для
запрошенной microversion. Отдельный envelope не нужен.

### Required tests

Минимальный набор backend-тестов:

- endpoint недоступен до microversion `1.5`;
- `RECOMMENDED -> CANCELLED`;
- `PENDING -> CANCELLED`;
- `ONGOING -> CANCELLING`;
- invalid source states возвращают ошибку;
- unknown action plan возвращает `404`;
- policy denied возвращает существующий forbidden response;
- actions текущего action plan отменяются при immediate `CANCELLED`;
- actions другого action plan не меняются;
- existing PATCH cancel behavior остается рабочим.

## P2.2: `audit_template_uuid` в audit response body

Статус реализации: реализовано в backend API microversion `1.6`.

### Новое поле

```json
{
  "audit_template_uuid": "3d9b5f5d-6f83-4c20-bd25-2bafcbb964f8"
}
```

Поле появляется только при:

```http
OpenStack-API-Version: infra-optim 1.6
```

Важно: numeric `audit_template_id` остается internal-only и не должен
попадать в REST response body.

### Где поле должно появиться

Поле `audit_template_uuid` должно быть доступно в:

```http
GET /v1/audits
GET /v1/audits/detail
GET /v1/audits/<audit_uuid>
POST /v1/audits
```

Для microversions ниже `1.6` response body остается прежним.

### Значение поля

Контракт значения:

- audit создан через `audit_template_uuid`: возвращается UUID template;
- audit создан напрямую через `goal`: возвращается `null`;
- template был purge/hard-delete и связь очищена: возвращается `null`;
- если внутренний `audit_template_id` указывает на отсутствующую template,
  backend не должен падать, поле возвращается как `null`.

### Performance constraint

List endpoints не должны делать отдельный DB lookup на каждую строку при
обычной пагинации. Предпочтительные варианты:

- добавить object/db helper, который строит mapping `audit_template_id -> uuid`
  для текущей страницы audits;
- либо расширить существующий DB query/object layer так, чтобы template UUID
  подтягивался вместе с audits.

Прямой `AuditTemplate.get_by_id()` внутри property допустим только для single
audit/detail create path, но не как единственный механизм для list endpoints.

### Required tests

Минимальный набор backend-тестов:

- поле отсутствует до microversion `1.6`;
- поле есть и заполнено для template-backed audit при `1.6`;
- поле равно `null` для goal-only audit;
- поле равно `null` после hard-delete/purge template;
- `audit_template_id` не появляется в response body;
- list/detail/single/create responses покрыты отдельно;
- существующий `audit_template_uuid` query filter продолжает работать.

## P2.3: `detail` flag для Data Model API

### Новый query parameter

```http
GET /v1/data_model?detail=true
OpenStack-API-Version: infra-optim 1.7
```

Default:

```text
detail=false
```

Это сохраняет текущий контракт:

```http
GET /v1/data_model
GET /v1/data_model?data_model_type=compute
GET /v1/data_model?data_model_type=compute&audit_uuid=<AUDIT_UUID>
```

### API -> RPC -> Decision Engine flow

Новый параметр должен проходить через весь путь:

```text
DataModelController.get_all(detail=False)
DecisionEngineAPI.get_data_model_info(..., detail=False)
DataModelEndpoint.get_data_model_info(..., detail=False)
```

Для `detail=false` endpoint возвращает текущий результат
`available_data_model.to_list()`.

Для `detail=true` нужно использовать только стабильный serializer data model.
Если в Common Data Model нет устойчивого detailed serializer, реализацию
следует отложить и оставить P2.3 в статусе design-only. Нельзя возвращать
случайные internal Python-object dumps, потому что это сразу станет публичным
REST contract.

### Validation

Контракт параметра:

- `detail=true`, `detail=True`, `detail=1` трактуются как `True`;
- `detail=false`, `detail=False`, `detail=0` трактуются как `False`;
- invalid boolean value возвращает `400 Bad Request`;
- параметр недоступен до microversion `1.7`.

### Required tests

Минимальный набор backend-тестов:

- до microversion `1.7` запрос с параметром `detail` возвращает
  `406 Not Acceptable`;
- default behavior без `detail` не меняется;
- `detail=false` возвращает текущий compact result;
- `detail=true` вызывает RPC с `detail=True`;
- invalid boolean возвращает `400`;
- invalid `data_model_type` продолжает возвращать `404`;
- `audit_uuid` продолжает передаваться в Decision Engine API.

## Backfill historical audits

Backfill старых audits для `audit_template_id` не входит в immediate P2 API
implementation.

Причина: для historical audits нет гарантированного источника истины, если
связь с template раньше не сохранялась. Нельзя восстанавливать
`audit_template_id` эвристически по goal/strategy/name без риска связать audit
с неправильной template.

Допустимый будущий вариант:

```text
watcher-db-manage audit-template-backfill --dry-run
watcher-db-manage audit-template-backfill --apply
```

Ограничения такого инструмента:

- по умолчанию только dry-run/report;
- apply разрешен только для детерминированных совпадений;
- все изменения логируются;
- repeated run должен быть idempotent;
- ambiguous matches не изменяются автоматически.

Этот пункт лучше считать P3/maintenance task, а не частью публичного P2 API.

## Implementation order

Рекомендуемый порядок реализации:

1. Добавить microversion `1.5` и `POST /v1/action_plans/<uuid>/cancel`.
2. Добавить api-ref/releasenote/tests для action plan cancel.
3. Добавить microversion `1.6` и `audit_template_uuid` response field.
4. Добавить api-ref/releasenote/tests для audit template UUID response.
5. Проверить наличие стабильного detailed serializer для data model.
6. Если serializer есть, добавить microversion `1.7` и `detail` flag.
7. Если serializer нет, оставить P2.3 design-only до отдельного решения.

## Verification matrix

Перед merge P2 должны пройти:

```text
watcher.tests.api.v1.test_action_plan
watcher.tests.api.v1.test_audits
watcher.tests.api.v1.test_data_model
watcher.tests.api.v1.test_versions
```

Дополнительно:

```text
python -m py_compile <changed python files>
git diff --check
sphinx/api-ref build, если меняется api-ref
releasenotes build, если добавляются release notes
```

## Horizon integration notes

Для Horizon plugin после P2:

- cancel button должен использовать dedicated cancel endpoint только если
  service catalog/version discovery показывает API `>= 1.5`;
- audit list/detail может читать `audit_template_uuid` только при API `>= 1.6`;
- data model detailed view может включать `detail=true` только при API
  `>= 1.7`;
- для старых endpoints Horizon должен сохранять fallback:
  PATCH cancel, отсутствие `audit_template_uuid`, compact data model.
