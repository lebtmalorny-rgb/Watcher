# Codex Task — OpenStack Watcher backend API and pagination improvements

## Target repository

Use this task in the **OpenStack Watcher backend** repository, for example:

```bash
git clone https://opendev.org/openstack/watcher.git
cd watcher
git checkout stable/2025.1
```

This task is for the backend/API service only. A separate Horizon plugin will consume the API changes.

## Background

The downstream validation matrix for OpenStack Epoxy / 2025.1 shows that several Watcher capabilities are available through OSC/API but are missing or difficult to consume from Horizon. It also shows backend-side gaps that make a clean Horizon implementation harder:

- `GET /v1/audits?goal=<name>` works.
- `GET /v1/audits?strategy=<name>` works.
- `GET /v1/audits?sort_key=name&sort_dir=desc` works.
- `GET /v1/audits?limit=2&marker=<uuid>` works.
- `GET /v1/audits?state=PENDING` currently returns HTTP 400 `Unknown argument: state`.
- `GET /v1/audits?audit_template_uuid=<uuid>` currently returns HTTP 400 `Unknown argument: audit_template_uuid`.
- `openstack optimize audit create` can store `start_time`, `end_time`, `force`, `EVENT`, `parameters`, `interval`, and `auto_trigger`, but these behaviors need backend regression coverage.
- `openstack optimize datamodel list` without a type can time out in the tested environment.
- `actionplan cancel` and `actionplan update` exist in OSC and should be backed by stable API behavior.

## Primary goal

Improve and harden Watcher backend API behavior so a separate Horizon plugin can implement full Watcher UI parity without client-side hacks.

This task is **not** about Horizon UI implementation.

## Hard boundaries

1. Modify only the `openstack/watcher` backend repository.
2. Do not modify Horizon, watcher-dashboard, or python-watcherclient.
3. Preserve backward compatibility for OpenStack Epoxy / 2025.1 unless a microversioned change is explicitly necessary.
4. Do not remove existing query parameters or response fields.
5. Do not change public response shapes unless there is an existing Watcher API convention for the change.
6. Add unit/API tests for every behavior changed.
7. Update API reference and release notes for user-visible API changes.
8. Do not implement webhook triggering in this task, except for documenting it as out of scope.

## First steps for Codex

Before editing:

1. Inspect the Watcher API controllers, especially likely files such as:
   - `watcher/api/controllers/v1/audits.py`
   - `watcher/api/controllers/v1/audit_templates.py`
   - `watcher/api/controllers/v1/action_plans.py`
   - `watcher/api/controllers/v1/actions.py`
   - `watcher/api/controllers/v1/data_model.py`
   - `watcher/api/controllers/v1/services.py`
   - `watcher/api/controllers/v1/scoring_engines.py`
   - `watcher/api/controllers/v1/strategies.py`
2. Trace list calls down to DB/object layer methods.
3. Identify existing helper code for:
   - query parameter validation;
   - filtering;
   - sort key validation;
   - `limit` / `marker` pagination;
   - API microversions;
   - functional API tests.
4. Reuse existing Watcher patterns. Do not invent a new pagination framework if one already exists.
5. Produce a concise file-level plan before implementing changes.

## P0 backend requirements

### 1. Audits list: add backend-supported filters needed by Horizon

Current known behavior:

```http
GET /v1/audits?goal=server_consolidation        -> 200
GET /v1/audits?strategy=basic                   -> 200
GET /v1/audits?state=PENDING                    -> 400 Unknown argument
GET /v1/audits?audit_template_uuid=<uuid>       -> 400 Unknown argument
```

Implement server-side support for:

```http
GET /v1/audits?state=<state>
GET /v1/audits?audit_template_uuid=<uuid>
```

#### Required behavior for `state`

- Accept valid Watcher audit states only.
- Normalize state consistently with existing Watcher state constants.
- Invalid states should return a clear 400 response.
- Filtering must happen before pagination.
- Filtering must happen in the DB/object layer where practical, not by loading all audits into memory.

Suggested valid examples:

```text
PENDING
ONGOING
SUCCEEDED
FAILED
CANCELLED
SUSPENDED
DELETED
```

Use the actual constants available in the repository rather than hardcoding if possible.

#### Required behavior for `audit_template_uuid`

- Accept a UUID value.
- Return only audits whose `audit_template_uuid` matches.
- Invalid UUID format should return the project’s standard invalid query response.
- Unknown UUID should return an empty list, unless the existing API pattern says otherwise.
- Filtering must happen before pagination.

#### Do not break existing behavior

These must continue to work:

```http
GET /v1/audits?goal=<goal_name_or_uuid>
GET /v1/audits?strategy=<strategy_name_or_uuid>
GET /v1/audits?limit=<n>
GET /v1/audits?marker=<audit_uuid>
GET /v1/audits?sort_key=<field>&sort_dir=asc|desc
```

### 2. Audits list: harden pagination and sorting

Ensure `GET /v1/audits` handles the following consistently:

| Parameter | Required behavior |
|---|---|
| `limit` | Limit returned rows. Validate type and max value using existing Watcher conventions. |
| `marker` | Cursor marker by audit UUID. Invalid marker should use the existing API error style. |
| `sort_key` | Validate against an allowed sort field list. Reject invalid values clearly. |
| `sort_dir` | Accept only `asc` and `desc`, following existing case-sensitivity conventions. |
| filters + pagination | Apply filters first, then sort, then paginate. |
| deterministic ordering | If no sort is provided, preserve existing default order. If ordering is unstable, add a stable tie-breaker using existing DB pattern. |

Add tests proving that these combinations work together:

```http
GET /v1/audits?goal=server_consolidation&limit=2
GET /v1/audits?strategy=basic&sort_key=name&sort_dir=desc
GET /v1/audits?state=PENDING&limit=2
GET /v1/audits?audit_template_uuid=<uuid>&sort_key=updated_at&sort_dir=desc
GET /v1/audits?goal=server_consolidation&strategy=basic&state=PENDING&limit=2&marker=<uuid>
```

### 3. Audit create: add or harden regression coverage

The validation matrix shows OSC can create audits using fields that Horizon must later expose.

Ensure backend behavior is covered by tests for:

| Field | Expected behavior |
|---|---|
| `audit_type=ONESHOT` | Accepted. |
| `audit_type=CONTINUOUS` | Accepted only with valid top-level `interval`. |
| `audit_type=EVENT` | Accepted if the backend already supports it. If only partially supported, keep creation accepted but do not implement webhook execution here. |
| `interval` | Top-level string-compatible field. Required for `CONTINUOUS`. Do not treat it as a strategy parameter. |
| `auto_trigger` | Stored and returned. |
| `start_time` | Accepted and stored for scheduled/continuous audits. |
| `end_time` | Accepted and stored for scheduled/continuous audits. |
| `force` | Accepted for non-`CONTINUOUS` audits. Rejected for `CONTINUOUS` with a clear 400 error. |
| `parameters` | Accepted as a dictionary/object; strategy defaults may be merged by existing strategy schema behavior. |

Example request body that should be tested:

```json
{
  "audit_template_uuid": "<template_uuid>",
  "audit_type": "CONTINUOUS",
  "name": "api-regression-continuous",
  "interval": "60",
  "auto_trigger": true,
  "start_time": "2026-12-31T23:00:00",
  "end_time": "2027-06-30T23:00:00",
  "parameters": {
    "period": 300,
    "migration_attempts": 5
  }
}
```

Example negative case:

```json
{
  "audit_template_uuid": "<template_uuid>",
  "audit_type": "CONTINUOUS",
  "name": "invalid-force-continuous",
  "interval": "60",
  "force": true
}
```

Expected result: 400 with a clear message that `force` is not allowed for continuous audits.

### 4. Audit update: verify PATCH coverage for Horizon-safe wrappers

Ensure API tests cover these PATCH operations:

```http
PATCH /v1/audits/<audit_uuid>
```

Rename:

```json
[
  {"op": "replace", "path": "/name", "value": "new-name"}
]
```

Cancel:

```json
[
  {"op": "replace", "path": "/state", "value": "CANCELLED"}
]
```

Required behavior:

- Rename should update `name` and `updated_at`.
- Cancel should work for states where Watcher already permits cancellation.
- Invalid state transitions should return the existing Watcher error style.
- Do not create a new custom cancel endpoint for audits unless the project already has that convention.

### 5. Action plan list/update/cancel API behavior

Ensure these are stable and tested:

```http
GET   /v1/action_plans?audit_uuid=<audit_uuid>&limit=<n>&marker=<uuid>&sort_key=<field>&sort_dir=asc|desc
PATCH /v1/action_plans/<action_plan_uuid>
POST  /v1/action_plans/<action_plan_uuid>/start
```

If the API already exposes a dedicated cancel endpoint, add tests for it. If cancellation is implemented through PATCH, ensure PATCH tests cover it.

Recommended cancel semantics:

- `PENDING` action plan -> `CANCELLED`
- `ONGOING` action plan -> `CANCELLING` or the state required by the existing Watcher state machine
- Invalid transitions should fail clearly

Patch example:

```json
[
  {"op": "replace", "path": "/state", "value": "CANCELLED"}
]
```

### 6. Audit templates list: verify filters and pagination

Ensure `GET /v1/audit_templates` supports and tests:

```http
GET /v1/audit_templates?goal=<goal_name_or_uuid>
GET /v1/audit_templates?strategy=<strategy_name_or_uuid>
GET /v1/audit_templates?limit=<n>&marker=<uuid>
GET /v1/audit_templates?sort_key=<field>&sort_dir=asc|desc
```

If some of these already work, add regression tests only.

### 7. Data model endpoint: prevent no-filter timeouts

The validation matrix shows `openstack optimize datamodel list` without a type can time out.

Investigate `GET /v1/data_model` and implement the least risky fix consistent with the Watcher API contract.

Preferred behavior for Horizon/plugin compatibility:

```http
GET /v1/data_model?data_model_type=compute
GET /v1/data_model?data_model_type=compute&detail=true
GET /v1/data_model?data_model_type=compute&audit_uuid=<audit_uuid>
```

Required work:

1. Ensure `data_model_type=compute` is efficient enough for normal Horizon use.
2. Ensure `audit_uuid=<uuid>` filtering works when provided.
3. Ensure `detail=true` is explicit and does not become the implicit default.
4. For missing `type`, choose one of the following after inspecting existing API expectations:
   - preserve old behavior but optimize it;
   - default safely to `compute` if compatible;
   - return a clear 400 that asks the client to specify `type`, only if this does not violate the intended API contract or if protected by a microversion.
5. Add tests for the selected behavior.

Do not silently run an unbounded expensive query if it is known to time out.

### 8. Services, scoring engines, and strategy state

Verify or add API tests for read-only diagnostic endpoints that the Horizon plugin will consume:

```http
GET /v1/services
GET /v1/services/<service_id>
GET /v1/scoring_engines
GET /v1/scoring_engines/<scoring_engine_id>
GET /v1/strategies/<strategy_name>/state
```

For list endpoints, verify or add support for the standard list parameters where the API already claims to support them:

```text
detail
limit
marker
sort_key
sort_dir
```

Do not add write actions for these resources unless already present in Watcher.

## Query parameter policy

### Known supported for audits after this task

The final audit list should support at least:

```text
goal
strategy
state
audit_template_uuid
limit
marker
sort_key
sort_dir
```

### Unknown arguments

Keep the existing strict behavior for truly unknown arguments. For example:

```http
GET /v1/audits?random_field=value
```

should still fail according to the current Watcher API validation pattern.

## Tests to add or update

Add tests in the existing Watcher test structure. Use existing fixtures/factories.

Minimum test list:

1. `test_audit_list_filter_by_goal`
2. `test_audit_list_filter_by_strategy`
3. `test_audit_list_filter_by_state`
4. `test_audit_list_filter_by_audit_template_uuid`
5. `test_audit_list_filter_state_and_pagination`
6. `test_audit_list_filter_template_and_sort_desc`
7. `test_audit_list_invalid_state_returns_400`
8. `test_audit_list_invalid_template_uuid_returns_400`
9. `test_audit_create_continuous_with_start_end_interval_auto_trigger`
10. `test_audit_create_event_type`
11. `test_audit_create_force_oneshot`
12. `test_audit_create_force_continuous_returns_400`
13. `test_audit_update_replace_name`
14. `test_audit_update_replace_state_cancelled`
15. `test_actionplan_list_pagination_sorting`
16. `test_actionplan_update_replace_state_cancelled`
17. `test_datamodel_list_default_or_missing_type_behavior`
18. `test_datamodel_list_compute_with_detail_false`
19. `test_strategy_state_endpoint`
20. `test_services_list_pagination_if_supported`
21. `test_scoring_engines_list_pagination_if_supported`

Use exact naming conventions from the repository.

## Documentation and release notes

Update the API reference or developer docs for:

- new `audits` filters: `state`, `audit_template_uuid`;
- combined filters with `limit` and `marker`;
- valid audit create fields: `EVENT`, `start_time`, `end_time`, `force`, `interval`, `auto_trigger`, `parameters`;
- datamodel `type` recommendation or requirement;
- action plan cancel/update behavior if not clearly documented.

Add a release note, for example:

```yaml
---
features:
  - |
    Added server-side audit filters for state and audit template UUID, enabling
    Horizon and other API clients to use paginated audit views without loading
    all audits client-side.
fixes:
  - |
    Hardened audit list pagination/sorting behavior and added regression
    coverage for scheduled audit create fields used by OSC.
```

Adjust wording to match the actual code changes.

## Validation commands

Run the project’s normal checks. At minimum, try:

```bash
tox -e py3
tox -e pep8
```

If the repository defines more specific API tests, run the relevant subset as well.

Also prepare manual validation commands for a deployed cloud:

```bash
openstack optimize audit list --goal server_consolidation --limit 2
openstack optimize audit list --strategy basic --sort-key name --sort-dir desc
openstack optimize audit list --limit 2 --marker <audit_uuid>

# After backend filter support is implemented, these should work:
openstack optimize audit list --state PENDING
openstack optimize audit list --audit-template <audit_template_uuid>

openstack optimize audit create \
  -t CONTINUOUS \
  -i 60 \
  --start-time '2026-12-31 23:00:00' \
  --end-time '2027-06-30 23:00:00' \
  --auto-trigger \
  -a <audit_template> \
  --name api-regression-continuous

openstack optimize audit create \
  -t ONESHOT \
  --force \
  -a <audit_template> \
  --name api-regression-force

openstack optimize datamodel list --type compute
openstack optimize strategy state <strategy_name>
openstack optimize service list
```

If OSC does not yet expose a newly added backend query flag, validate using direct HTTP/API tests and document that OSC support is separate.

## Definition of done

The task is complete when:

1. Audit list supports server-side `state` and `audit_template_uuid` filters.
2. Audit list filters combine correctly with `goal`, `strategy`, `limit`, `marker`, `sort_key`, and `sort_dir`.
3. Audit create fields used by OSC have backend regression tests.
4. Audit PATCH rename/cancel behavior has regression tests.
5. Action plan cancel/update behavior has regression tests.
6. Data model endpoint no longer encourages or performs an unbounded timeout-prone default path without a clear contract.
7. API docs/release notes are updated for user-visible changes.
8. `tox -e py3` and `tox -e pep8` pass or any failures are unrelated and clearly documented.
9. A final summary lists changed files, tests run, and any intentionally deferred work.

## Out of scope

Do not implement these in this backend task:

- Horizon plugin UI;
- Horizon forms/tables/views;
- client-side pagination components;
- webhook trigger UI;
- large refactoring of Watcher strategy engine;
- new scoring engine write operations;
- direct shell usage of `openstack` from services.
