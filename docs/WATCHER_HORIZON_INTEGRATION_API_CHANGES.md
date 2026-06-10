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
- document and regression-test the existing audit create contract used by UI
  clients;
- reject `force=True` when creating `CONTINUOUS` audits, because force applies
  to immediate non-continuous execution and is ambiguous for scheduled audits;
- keep the Audit response schema unchanged;
- keep the database schema unchanged;
- keep the Watcher versioned object schema unchanged.

The goal is to let Horizon filter audit lists server-side without requiring
client-side filtering or a database migration.

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

## Data Model Changes

There are no database schema changes for the `state` filter.

Unchanged database model:

```text
audits.state
```

The existing `audits.state` column is already supported by the SQLAlchemy DB
filter helper. The API now exposes that existing capability through REST.

There are no changes to:

- `watcher/db/sqlalchemy/models.py`;
- Alembic migration scripts;
- `watcher/objects/audit.py` fields;
- Audit object version;
- Audit response body fields.

Because the Audit object schema is unchanged, existing Watcher clients and
Horizon code that deserialize audit responses do not need model updates for
this feature.

## Horizon Plugin Contract

Recommended capability flags for a Horizon Watcher plugin:

```python
WATCHER_BACKEND_SUPPORTS_AUDIT_STATE_FILTER = True
WATCHER_BACKEND_SUPPORTS_AUDIT_TEMPLATE_FILTER = False
```

Recommended UI behavior:

- use server-side `state` filtering for audit list views;
- send only valid uppercase Watcher audit states;
- follow Watcher-provided `next` links for pagination;
- omit `force` for `CONTINUOUS` audit creation and expose it only where the UI
  creates immediate non-continuous audits under the existing microversion
  contract;
- send strategy `parameters` only after validating them against the selected
  strategy schema exposed by Watcher;
- do not emulate `audit_template_uuid` filtering client-side unless the plugin
  has already fetched all relevant pages and explicitly labels the result as
  client-filtered.

## Explicit Non-Change: Audit Template Filter

`GET /v1/audits?audit_template_uuid=<UUID>` is not implemented in this patch.

Reason:

- `AuditPostType` accepts `audit_template_uuid` when creating an audit;
- Watcher uses the template to derive audit fields such as goal, strategy,
  scope, and default name;
- the created Audit row does not persist `audit_template_uuid`;
- the Epoxy `audits` table has no `audit_template_id` or
  `audit_template_uuid` column.

Adding a correct `audit_template_uuid` audit list filter requires a separate
schema-changing task:

- database migration;
- SQLAlchemy model update;
- Audit object field and object version update;
- create-path persistence of the template identity;
- API compatibility decision for response exposure;
- DB/API tests;
- api-ref and release notes.

Until that separate task is implemented, Horizon should not assume server-side
audit-template filtering is available.

## Files Changed

Code:

```text
watcher/api/controllers/v1/audit.py
watcher/tests/api/v1/test_audits.py
```

Documentation:

```text
api-ref/source/parameters.yaml
api-ref/source/watcher-api-v1-audits.inc
docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md
releasenotes/notes/audit-state-query-filter-2ad0c3df0af66f13.yaml
```
