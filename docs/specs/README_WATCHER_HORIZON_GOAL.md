# Общая цель backend-доработок Watcher для Horizon

Цель этой ветки - подготовить backend Watcher под OpenStack Epoxy / 2025.1
так, чтобы отдельный Horizon Watcher plugin мог работать с ним через
нормальный REST API, без UI-side hacks и без поломки существующих клиентов.

Речь идет именно о backend-контракте Watcher. Сам Horizon plugin и
интеграционные тесты plugin-а сейчас не входят в scope.

## Что это означает практически

- Horizon должен получать нужные фильтры и поля от backend, а не вычислять
  связи между сущностями на клиентской стороне.
- Старые клиенты, watcherclient и OSC не должны ломаться от новых response
  fields или endpoint-ов.
- Все новые публичные возможности должны включаться через microversions.
- Изменения модели данных и API должны быть явно задокументированы.
- Поведение, важное для UI, должно быть закреплено backend regression-тестами.
- Опасные maintenance-действия, например backfill старых audits, не должны
  выполняться автоматически без отдельного безопасного дизайна.

## Текущий фокус

P0/P1 уже закрывают безопасную backend-основу:

- server-side фильтры audits;
- связь audit с audit template на уровне модели данных;
- regression coverage для важных API-сценариев;
- документацию фактического backend-контракта.

P2 добавляет новые публичные возможности для Horizon, но только через новые
microversions:

- `1.5`: dedicated cancel endpoint для action plans;
- `1.6`: `audit_template_uuid` в audit response body;
- `1.7`: `detail=true` для `GET /v1/data_model`.

Для `GET /v1/data_model?detail=true` целевой backend-контракт в `1.7` - raw
XML-строка в поле `context`, полученная через стабильный serializer data
model. Compact response без `detail` не меняется.

Главное правило для всей работы: улучшать backend-контракт для Horizon, но не
ломать существующий Watcher API.
