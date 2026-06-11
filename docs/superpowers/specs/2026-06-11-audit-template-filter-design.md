# Audit Template Filter Design

Date: 2026-06-11
Branch: `feature/audit-state-filter-2025.1`
Base: Watcher Epoxy 2025.1

## Goal

Add a correct server-side `audit_template_uuid` filter for audit listing:

```http
GET /v1/audits?audit_template_uuid=<uuid>
GET /v1/audits/detail?audit_template_uuid=<uuid>
```

The implementation must preserve the existing Watcher API behavior for current
clients and make the backend safe for Horizon Watcher plugin integration.

## Current State

`AuditPostType` already accepts `audit_template_uuid` when creating an audit.
The controller uses the template to fill missing goal, strategy, scope, and
default name values, then creates an `Audit`.

The created audit does not currently retain the audit template identity:

- SQLAlchemy `audits` has no `audit_template_id` column.
- `objects.Audit` has no `audit_template_id` field.
- `_add_audits_filters()` has no `audit_template_uuid` filter.
- `GET /v1/audits?audit_template_uuid=...` is unsupported.

Filtering by audit template cannot be implemented correctly without storing the
audit-to-template relationship.

## API Design

Add `audit_template_uuid` as an optional query parameter to:

- `GET /v1/audits`
- `GET /v1/audits/detail`

Behavior:

- The value must be a UUID string.
- A valid UUID with no matching audit template or no matching audits returns an
  empty collection.
- The filter composes with existing `state`, `goal`, `strategy`, `limit`,
  `marker`, `sort_key`, and `sort_dir` behavior.
- Pagination `next` links preserve `audit_template_uuid`.
- Existing response fields are not expanded in this change.

Rationale for not adding `audit_template_uuid` to the response now:

- The immediate Horizon need is server-side filtering.
- Keeping the response unchanged reduces compatibility risk.
- Exposing the field can be added later as a separate API expansion if the
  plugin needs to display the originating template for each audit.

## Data Model Design

Add a nullable FK column:

```text
audits.audit_template_id -> audit_templates.id
```

The column is nullable because existing audits, and audits created directly from
`goal`, may not have an originating audit template.

SQLAlchemy model changes:

- Add `Audit.audit_template_id`.
- Add `Audit.audit_template` relationship.

Object model changes:

- Add nullable `audit_template_id` to `objects.Audit.fields`.
- Bump `objects.Audit.VERSION`.
- Do not add `audit_template_uuid` or `audit_template` to the API `Audit`
  representation in this task. The API class skips object fields that do not
  have matching API attributes, so `audit_template_id` remains internal.

Database migration:

- Add Alembic migration after `609bec748f2a`.
- Add nullable `audit_template_id` to `audits`.
- Add a foreign key to `audit_templates.id`.
- Downgrade removes the FK and column.

Existing rows are not backfilled. There is no reliable historical link between
older audits and audit templates because the value was not persisted.

## Create Flow

When `POST /v1/audits` includes `audit_template_uuid`:

1. Resolve the audit template as today.
2. Use it to fill missing goal, strategy, scope, and name as today.
3. Store the resolved `audit_template.id` in the new audit.

When the request uses `goal` without `audit_template_uuid`:

- Keep `audit_template_id` unset.

Existing validation remains:

- `audit_template_uuid` and `goal` are mutually exclusive.
- Missing both remains invalid.
- Invalid audit template UUID remains `400 Bad Request`.

## Query Flow

Controller:

- Accept `audit_template_uuid` in the audit collection methods.
- Add it to the DB filters when provided.
- Preserve it in collection `next` links.

DB API:

- Extend `_add_audits_filters()` to support `audit_template_uuid`.
- Use a relationship or join filter against the same audit row.
- Preserve the existing correlated `goal` and `strategy` filter behavior.

## Compatibility

Backward compatibility constraints:

- Existing audit create requests continue to work.
- Existing audit list/detail responses keep their current shape.
- Existing filters continue to behave as they do on this branch.
- Existing rows remain listable and sortable.
- Audits created without a template are excluded only when an
  `audit_template_uuid` filter is explicitly applied.

Horizon plugin contract:

- Horizon may send `audit_template_uuid` only when this backend capability is
  deployed.
- Horizon should not assume older audits can be matched to templates.
- If Horizon needs to display the template UUID per audit, that is a separate
  response-field enhancement.

## Tests

Add failing tests before implementation:

- API list filters audits by `audit_template_uuid`.
- API detail filters audits by `audit_template_uuid`.
- API list combines `audit_template_uuid` with `state`, `goal`, and `strategy`.
- API pagination `next` link preserves `audit_template_uuid`.
- API create with `audit_template_uuid` persists the relationship.
- DB list filters by `audit_template_uuid`.
- DB list combines `audit_template_uuid` with existing correlated filters.

Run focused tests first, then relevant full files:

```text
watcher.tests.api.v1.test_audits
watcher.tests.db.test_audit
```

Also run:

```text
python -m py_compile watcher/api/controllers/v1/audit.py watcher/objects/audit.py watcher/db/sqlalchemy/models.py
git diff --check
```

Run API reference and releasenotes builds if api-ref or release note files are
changed.

## Documentation

Update:

- `docs/WATCHER_EPOXY_2025_1_ANALYSIS.md`
- `docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md`
- API reference parameter documentation for audits and audits detail
- release note for the new audit list filter and persisted relationship

Documentation must explicitly state:

- `audit_template_uuid` is now a server-side filter.
- The filter only matches audits created after the relationship is persisted, or
  audits whose `audit_template_id` was otherwise populated.
- The API response shape is unchanged by this task.

## Non-Goals

This task does not:

- Add `audit_template_uuid` to audit response bodies.
- Backfill historical audits.
- Add a client-side fallback in Horizon.
- Change audit template create/update/delete behavior.
- Change the mutual exclusion between `goal` and `audit_template_uuid` on audit
  creation.
