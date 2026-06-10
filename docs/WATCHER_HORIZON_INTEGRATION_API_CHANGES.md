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

The current implemented change is intentionally small and backward-compatible:

- add an optional audit `state` query filter to audit collection APIs;
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
