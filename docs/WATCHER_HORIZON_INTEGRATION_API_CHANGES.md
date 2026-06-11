# Watcher Horizon Integration API Changes

Date: 2026-06-10

Target branch:

```text
stable/2025.1
```

Base release:

```text
OpenStack Epoxy / 2025.1
```

## Scope

This document describes Watcher backend changes that are relevant for a
standalone Horizon Watcher plugin.

The current implemented changes are intentionally small and backward-compatible:

- add an optional audit `state` query filter to audit collection APIs;
- add an optional audit `audit_template_uuid` query filter to audit collection
  APIs;
- persist the source audit template for newly created template-backed audits in
  nullable `audits.audit_template_id`;
- document and regression-test the existing audit create contract used by UI
  clients;
- reject `force=True` when creating `CONTINUOUS` audits, because force applies
  to immediate non-continuous execution and is ambiguous for scheduled audits;
- keep the Audit response schema unchanged.

The goal is to let Horizon filter audit lists server-side without requiring
client-side filtering. The audit-template filter includes a nullable database
migration and an Audit object version bump, but does not add audit-template
fields to audit API responses.

## API Changes

### List audits filtered by state

Endpoint:

```http
GET /v1/audits?state=<STATE>
```

The `state` query parameter is optional. When omitted, existing behavior is
preserved.

Accepted values:

```text
PENDING
ONGOING
SUCCEEDED
FAILED
CANCELLED
SUSPENDED
DELETED
```

The value is matched exactly. Horizon should send the uppercase constants
returned by Watcher.

Example:

```http
GET /v1/audits?state=PENDING
```

### List detailed audits filtered by state

Endpoint:

```http
GET /v1/audits/detail?state=<STATE>
```

The same `state` query parameter is available on the detailed list endpoint.
This keeps compact and detailed audit list views consistent for UI consumers.

Example:

```http
GET /v1/audits/detail?state=SUCCEEDED
```

### Combined filters

`state` can be combined with the existing compact audit list filters.

```http
GET /v1/audits?goal=<GOAL_UUID_OR_NAME>&state=PENDING
```

```http
GET /v1/audits?strategy=<STRATEGY_UUID_OR_NAME>&state=PENDING
```

```http
GET /v1/audits?goal=<GOAL_UUID_OR_NAME>&strategy=<STRATEGY_UUID_OR_NAME>&state=PENDING
```

The backend applies all filters together before pagination.

For `GET /v1/audits/detail`, this change adds only the `state` filter. Existing
documented behavior around `goal`, pagination, and sorting is unchanged.

### Pagination

Filtered collection responses preserve active filters in the `next` link.

Example first request:

```http
GET /v1/audits?state=PENDING&limit=2
```

The returned `next` URL includes the same `state=PENDING` filter together with
`limit` and `marker`. Horizon should follow the returned `next` link as-is
instead of rebuilding it manually.

### Invalid state

Invalid state values return `400 Bad Request`.

Example:

```http
GET /v1/audits?state=UNKNOWN
```

Expected result:

```text
400 Bad Request
```

Horizon should treat this as a client-side validation/configuration error, not
as an empty audit list.

### Deleted audits

`DELETED` is a valid audit state, but Watcher soft-deleted records are still
controlled by the existing deleted-record visibility behavior. Filtering by
`state=DELETED` only returns deleted audits when the request context/header
allows deleted records.

### Create audits compatibility contract

Endpoint:

```http
POST /v1/audits
```

This patch does not add request or response fields to audit creation. It
clarifies and tests the behavior Horizon can rely on when creating audits:

- `audit_type=ONESHOT` keeps the existing immediate execution behavior.
  `force` remains available through the existing microversion contract.
- `audit_type=CONTINUOUS` requires `interval`. Plain second intervals and
  cron-style intervals keep their existing behavior.
- invalid `interval` values for `audit_type=CONTINUOUS` return
  `400 Bad Request`.
- `audit_type=CONTINUOUS` accepts and returns `auto_trigger`.
- `audit_type=CONTINUOUS` with `force=True` returns `400 Bad Request`.
  Horizon should omit `force` or send `false` for scheduled continuous audits.
- `audit_type=EVENT` can be created without `interval` and starts in
  `PENDING`.
- `parameters` are accepted for template-backed audits when they match the
  selected strategy schema. Existing validation still rejects unknown
  parameters, missing required parameters, or invalid parameter values.

No API microversion, response body schema, database column, or Watcher object
version changes are required for this create-path validation.

### List action plans with preserved filters

Endpoint:

```http
GET /v1/action_plans?audit_uuid=<AUDIT_UUID>&strategy=<STRATEGY_UUID_OR_NAME>
```

This patch keeps the existing action plan list query parameters and fixes their
pagination behavior:

- `audit_uuid` and `strategy` are applied together to the same action plan row;
- filtered collection `next` links preserve `audit_uuid` and `strategy`;
- Horizon should follow Watcher-provided `next` links instead of rebuilding
  pagination URLs manually.

Example first request:

```http
GET /v1/action_plans?audit_uuid=<AUDIT_UUID>&strategy=<STRATEGY_UUID>&limit=2
```

The returned `next` URL includes the same `audit_uuid` and `strategy` filters
together with `limit` and `marker`.

## Data Model Changes

The `state` filter does not require a schema change.

Existing database model used by the `state` filter:

```text
audits.state
```

The existing `audits.state` column is already supported by the SQLAlchemy DB
filter helper. The API now exposes that existing capability through REST.

The `audit_template_uuid` filter adds a persisted audit-to-audit-template
relationship for newly created template-backed audits:

```text
audits.audit_template_id -> audit_templates.id ON DELETE SET NULL
```

Data model integration details:

- `watcher/db/sqlalchemy/models.py` adds nullable `Audit.audit_template_id`
  and an `Audit.audit_template` relationship.
- Alembic revision `c2f4b8d6e3a1` adds the nullable column and foreign key
  with `ON DELETE SET NULL`.
- `watcher/objects/audit.py` adds nullable `audit_template_id` and bumps the
  Audit object version.
- `watcher/api/controllers/v1/audit.py` stores the resolved template id when
  an audit is created with `audit_template_uuid`.
- Historical audits are not backfilled.
- If a source audit template is hard-deleted or purged, existing audits remain
  and their `audit_template_id` is cleared by the database.
- Audit response body fields are unchanged for API microversions below `1.6`.
- Starting with API microversion `1.6`, Audit responses expose public
  `audit_template_uuid`; the internal numeric `audit_template_id` remains
  hidden.

Because the Audit response schema is expanded only behind microversion `1.6`,
existing Watcher clients and Horizon code that request older microversions do
not need response model updates for this feature.

## Horizon Plugin Contract

Recommended capability flags for a Horizon Watcher plugin:

```python
WATCHER_BACKEND_SUPPORTS_AUDIT_STATE_FILTER = True
WATCHER_BACKEND_SUPPORTS_AUDIT_TEMPLATE_FILTER = True
WATCHER_BACKEND_EXPOSES_AUDIT_TEMPLATE_UUID = True  # API >= 1.6
WATCHER_BACKEND_SUPPORTS_DATA_MODEL_DETAIL = True  # API >= 1.7
WATCHER_BACKEND_SUPPORTS_DATA_MODEL_JSON_DETAIL = True  # API >= 1.8
```

Recommended UI behavior:

- use server-side `state` filtering for audit list views;
- send only valid uppercase Watcher audit states;
- follow Watcher-provided `next` links for pagination;
- use `audit_uuid`, not `audit`, when filtering action plans by audit;
- follow filtered action plan `next` links as-is so `audit_uuid` and
  `strategy` filters remain active across pages;
- use server-side `audit_template_uuid` filtering when the backend capability
  flag is enabled;
- read `audit_template_uuid` from Audit response bodies only when API `>= 1.6`
  was negotiated;
- send `detail=true` to `GET /v1/data_model` only when API `>= 1.7` was
  negotiated;
- request `detail_format=json` only when API `>= 1.8` was negotiated;
- handle detailed data model `context` as an XML string when API is below
  `1.8`, or when `detail_format=json` was not requested;
- handle detailed data model `context` as a JSON object only for
  `detail=true&detail_format=json` with API `>= 1.8`;
- omit `force` for `CONTINUOUS` audit creation and expose it only where the UI
  creates immediate non-continuous audits under the existing microversion
  contract;
- send strategy `parameters` only after validating them against the selected
  strategy schema exposed by Watcher;
- do not emulate `audit_template_uuid` filtering client-side for this backend
  capability.

### Audit template filter

`GET /v1/audits?audit_template_uuid=<UUID>` and
`GET /v1/audits/detail?audit_template_uuid=<UUID>` are supported by this
branch.

The backend persists the source audit template as `audits.audit_template_id`
when an audit is created with `audit_template_uuid`. For API microversions
below `1.6`, the response body shape is unchanged. Starting with API `1.6`,
audit list/detail/single/create responses expose public `audit_template_uuid`.
The internal numeric `audit_template_id` is never exposed through REST.

Integration notes:

- Horizon may send `audit_template_uuid` when this backend capability is
  deployed.
- The filter matches audits that have a persisted `audit_template_id`.
- Historical audits created before this schema change are not backfilled and do
  not match the filter unless their `audit_template_id` is populated later.
- Audits created directly from `goal` have no audit template relationship and
  do not match the filter.
- Audits whose source audit template has been purged keep their audit history,
  but their cleared `audit_template_id` means they no longer match this filter.

### Data model detail

Starting with API microversion `1.7`, `GET /v1/data_model` accepts an optional
`detail` query parameter:

```http
GET /v1/data_model?detail=true
OpenStack-API-Version: infra-optim 1.7
```

Compatibility contract:

- omitting `detail` or setting `detail=false` preserves the existing compact
  response where `context` is a list from `available_data_model.to_list()`;
- `detail=true`, `detail=True`, and `detail=1` request detailed output;
- `detail=false`, `detail=False`, and `detail=0` request compact output;
- invalid values return `400 Bad Request`;
- sending the `detail` parameter before API `1.7` returns `406 Not
  Acceptable`.

Detailed output uses the existing stable data model serializer:

```text
available_data_model.to_string()
```

For the compute data model this means `context` is an XML string rooted at
`<ModelRoot>`. This is not a new JSON Common Data Model schema.

Starting with API microversion `1.8`, detailed data model output also accepts
an optional `detail_format` query parameter:

```http
GET /v1/data_model?detail=true&detail_format=json
OpenStack-API-Version: infra-optim 1.8
```

Compatibility contract:

- API `1.7`: `detail=true` keeps XML string `context`;
- API `1.8`: `detail=true` without `detail_format` keeps XML string
  `context`;
- API `1.8`: `detail=true&detail_format=xml` keeps XML string `context`;
- API `1.8`: `detail=true&detail_format=json` returns JSON object
  `context` when a scoped/latest data model is available;
- if no scoped/latest data model is available, `context` remains the existing
  empty list sentinel `[]`;
- `detail_format` requires `detail=true`;
- `detail_format` is unavailable before API `1.8`;
- invalid `detail_format` values return `400 Bad Request`.

The JSON detail envelope is:

```json
{
  "context": {
    "schema": "watcher.data_model.detail",
    "schema_version": "1.0",
    "model_type": "compute",
    "stale": false,
    "data": {
      "compute_nodes": [],
      "unmapped_instances": []
    }
  }
}
```

Horizon should request `detail_format=json` only after negotiating API
`>= 1.8`. The JSON schema is opt-in and does not replace the API `1.7` XML
detailed behavior. Horizon should still handle `context: []` as an empty data
model response for any detail format.

## Files Changed

Code:

```text
watcher/api/controllers/v1/types.py
watcher/api/controllers/v1/audit.py
watcher/api/controllers/v1/action_plan.py
watcher/api/controllers/v1/data_model.py
watcher/api/controllers/v1/utils.py
watcher/api/controllers/v1/versions.py
watcher/decision_engine/rpcapi.py
watcher/decision_engine/messaging/data_model_endpoint.py
watcher/db/sqlalchemy/api.py
watcher/db/sqlalchemy/models.py
watcher/db/sqlalchemy/alembic/versions/c2f4b8d6e3a1_add_audit_template_id_to_audits.py
watcher/objects/audit.py
watcher/tests/api/v1/test_audits.py
watcher/tests/api/v1/test_actions_plans.py
watcher/tests/api/v1/test_data_model.py
watcher/tests/api/v1/test_microversions.py
watcher/tests/decision_engine/test_rpcapi.py
watcher/tests/decision_engine/messaging/test_data_model_endpoint.py
watcher/tests/db/test_action_plan.py
watcher/tests/db/test_audit.py
watcher/tests/db/utils.py
watcher/tests/objects/test_objects.py
```

Documentation:

```text
api-ref/source/parameters.yaml
api-ref/source/watcher-api-v1-audits.inc
api-ref/source/watcher-api-v1-datamodel.inc
api-ref/source/samples/datamodel-list-json-detail-response.json
docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md
releasenotes/notes/audit-state-query-filter-2ad0c3df0af66f13.yaml
releasenotes/notes/audit-template-filter-4f65d2cb0dfd13f2.yaml
releasenotes/notes/data-model-detail-api-7d2e4a1f9c0b6e53.yaml
releasenotes/notes/data-model-json-detail-api-8c1d2e3f4a5b6c7d.yaml
```
