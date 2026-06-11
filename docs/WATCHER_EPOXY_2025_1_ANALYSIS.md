# Watcher Epoxy 2025.1 Analysis

Analysis date: 2026-06-10

Local repository:

```text
/Users/dmitry/Desktop/DRS:HA_fork/watcher
```

Base OpenStack release:

```text
Epoxy / 2025.1
```

Current local branch after switch:

```text
stable/2025.1
```

Current baseline commit:

```text
d6750e40 Add debug message to report calculated metric for workload_balance
```

Upstream remote:

```text
https://opendev.org/openstack/watcher.git
```

GitHub repository for this work:

```text
https://github.com/lebtmalorny-rgb/Watcher.git
```

## Master Backport Check

`origin/master` was fetched during analysis. Current checked master tip:

```text
62edf948 Merge "doc: Drop reference to "keystone" CLI"
```

Result:

- The missing `GET /v1/audits?state=...` filter is not present in
  `origin/master`.
- The missing `GET /v1/audits?audit_template_uuid=...` filter is not present in
  `origin/master`.
- Therefore these two filters cannot be solved by a simple cherry-pick from
  master. They need new implementation on `stable/2025.1`, with
  `audit_template_uuid` treated as schema-changing work if it remains required.

Master contains some nearby fixes, but the most relevant audit-create fixes are
already present on `stable/2025.1` through stable backports:

```text
de75a2a5 Merge "Return HTTP code 400 when creating an audit with wrong parameters" into stable/2025.1
c47f6fb6 Merge "Fix audit creation with no name and no goal or audit_template" into stable/2025.1
```

Potential master-only candidates to evaluate separately:

```text
0de5833b Freeze data_model API response fields
35aaaa92 Add option to filter action plans by hostname from db connection
```

These are not direct fixes for the requested audit filters. Backport them only
if the Horizon/API requirements explicitly need frozen data model response
fields or DB-side action plan hostname filtering.

## Higher Release Check

Also checked local remote branches:

```text
origin/stable/2025.2
origin/stable/2026.1
```

Result:

- `stable/2025.2` does not expose audit `state` as a REST list filter.
- `stable/2026.1` does not expose audit `state` as a REST list filter.
- `stable/2025.2` does not expose modern `audit_template_uuid` list filtering.
- `stable/2026.1` does not expose modern `audit_template_uuid` list filtering.
- The modern `audits` DB table in `stable/2026.1` still stores `goal_id`,
  `strategy_id`, and `scope`, but no audit-template foreign key or UUID.

There is a very old commit in history:

```text
8b8d2f01 Added audit_template filter to /audits/detail
```

That commit belongs to an older API/data model shape where audits carried
`audit_template_id` / `audit_template_uuid`. It is not directly backportable to
the Epoxy codebase because the modern Audit model no longer persists that
relationship.

## Console Location

Run Watcher commands from:

```bash
cd '/Users/dmitry/Desktop/DRS:HA_fork/watcher'
```

Do not run `tox`, `stestr`, or branch-changing `git` commands from the parent
`DRS:HA_fork/` directory unless the command explicitly uses `git -C watcher`.

## Actual Epoxy Test Layout

On `stable/2025.1`, API tests are under:

```text
watcher/tests/api/v1/
```

They are not under `watcher/tests/unit/api/v1/`, which appears in some newer
or generated task text.

Relevant files:

```text
watcher/tests/api/v1/test_audits.py
watcher/tests/api/v1/test_audit_templates.py
watcher/tests/api/v1/test_actions_plans.py
watcher/tests/api/v1/test_actions.py
watcher/tests/api/v1/test_data_model.py
watcher/tests/api/v1/test_services.py
watcher/tests/api/v1/test_scoring_engines.py
watcher/tests/api/v1/test_strategies.py
```

## Actual Epoxy API Controller Layout

The actual controller filenames are singular:

```text
watcher/api/controllers/v1/audit.py
watcher/api/controllers/v1/audit_template.py
watcher/api/controllers/v1/action_plan.py
watcher/api/controllers/v1/action.py
watcher/api/controllers/v1/data_model.py
watcher/api/controllers/v1/service.py
watcher/api/controllers/v1/scoring_engine.py
watcher/api/controllers/v1/strategy.py
```

Any implementation prompt that says `audits.py`, `audit_templates.py`,
`action_plans.py`, or `services.py` should be translated to these actual
Epoxy paths.

## Audit List Filters

Baseline REST behavior in `watcher/api/controllers/v1/audit.py` before this
patch:

- `GET /v1/audits?goal=...` is supported.
- `GET /v1/audits?strategy=...` is supported.
- `limit`, `marker`, `sort_key`, and `sort_dir` are supported.
- `state` is not exposed as a REST query parameter.
- `audit_template_uuid` is not exposed as a REST query parameter.
- `GET /v1/audits/detail` accepts `goal`, but does not expose `strategy`.

Current DB behavior in `watcher/db/sqlalchemy/api.py`:

- `_add_audits_filters()` already allows filtering by plain field `state`.
- `_add_audits_filters()` allows `goal_uuid`, `goal_name`, `strategy_uuid`,
  and `strategy_name`.
- `_add_audits_filters()` does not support `audit_template_uuid`.

Low-risk implementation:

1. Add `state` query parameter to `AuditsController._get_audits_collection()`.
2. Add `state` to `AuditsController.get_all()`.
3. Optionally add `state` and `strategy` to `AuditsController.detail()` for
   parity, if API compatibility is acceptable.
4. Validate `state` against `objects.audit.State`.
5. Pass `filters['state'] = state` before calling `objects.Audit.list()`.
6. Add API tests in `watcher/tests/api/v1/test_audits.py`.
7. Update API reference and release note.

Suggested tests:

```text
test_many_with_state_filter
test_many_with_state_filter_and_limit_keeps_next_filter
test_many_with_goal_and_state_filter
test_many_with_strategy_and_state_filter
test_many_with_goal_strategy_and_state_filter
test_many_with_invalid_state_filter
test_detail_with_state_filter
```

Implementation status on this branch:

- `GET /v1/audits?state=...` is implemented.
- `GET /v1/audits/detail?state=...` is implemented.
- `state` is validated against existing `objects.audit.State` constants.
- `GET /v1/audits?goal=...&strategy=...&state=...` is covered.
- Active filters are preserved in collection `next` links.
- No DB migration is required.
- No Audit object field or object version change is required.

Detailed Horizon integration contract:

```text
docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md
```

## Audit Template UUID Filter

This is not a simple query-parameter addition on Epoxy.

`AuditPostType` accepts `audit_template_uuid` at create time, but the value is
used only to copy template-derived fields into the audit:

```text
goal_id
strategy_id
scope
name default
```

The audit DB model does not store `audit_template_uuid`. The `audits` table has
no `audit_template_id` or `audit_template_uuid` column.

Consequence:

- `GET /v1/audits?audit_template_uuid=<uuid>` cannot be implemented correctly
  without adding persistent audit-template identity to the Audit model.
- A client-side or heuristic implementation based on goal/strategy/scope would
  be ambiguous and should be avoided.

Recommended decision:

- For a low-risk Epoxy backend patch, defer `audit_template_uuid` filtering and
  keep Horizon feature flag `WATCHER_BACKEND_SUPPORTS_AUDIT_TEMPLATE_FILTER =
  False`.
- If this filter is mandatory, make it a separate schema-changing task:
  migration, DB model, object field/version, create-path persistence,
  API response compatibility decision, tests, docs, and release note.

## Audit Create Coverage

Verified on this branch:

- `CONTINUOUS` with interval.
- cron-style interval.
- missing interval for `CONTINUOUS`.
- interval not allowed for `ONESHOT`.
- parameters validation with predefined strategy schema.
- start/end time for continuous audits behind microversion support.
- `force` for non-continuous audits.
- invalid interval for `CONTINUOUS` returns `400 Bad Request`.
- `EVENT` audit create starts in `PENDING` and does not trigger the Decision
  Engine immediately.
- `CONTINUOUS` audit create preserves `auto_trigger`.
- `CONTINUOUS` audit create with `force=True` returns `400 Bad Request`.
- template-backed audit create persists schema-valid strategy `parameters`.

Implemented regression tests:

```text
test_create_continuous_audit_with_wrong_interval
test_create_event_audit
test_create_continuous_audit_with_auto_trigger
test_create_continuous_audit_with_force_not_allowed
test_create_audit_with_strategy_parameters
```

## Audit PATCH

Already present:

- JSON PATCH for audit state.
- State transition validation through `AuditStateTransitionManager`.
- `updated_at` assertions in patch tests.

Coverage gap:

- Add an explicit rename test for `/name`, because Horizon wrappers will likely
  expose rename as a simple action.

Suggested test:

```text
test_replace_name_ok
```

## Action Plan API

Current REST behavior in `watcher/api/controllers/v1/action_plan.py`:

- `GET /v1/action_plans?audit_uuid=<uuid>` is supported.
- `strategy`, `limit`, `marker`, `sort_key`, and `sort_dir` are supported.
- PATCH state transitions are implemented.
- `POST /v1/action_plans/<uuid>/start` exists.
- No dedicated cancel endpoint is needed; cancel is PATCH-based.

Important naming point:

- The Epoxy API uses `audit_uuid`, not `audit`.
- Horizon/API wrapper specs should either use `audit_uuid` or explicitly map
  friendly UI names to the existing backend query parameter.

Already covered:

- `audit_uuid` filter tests.
- pagination tests.
- sort by `audit_uuid`.
- PATCH transition tests, including cancel transitions.
- `audit_uuid + strategy` combined filtering is correlated to the same action
  plan row.
- Filtered action plan `next` links preserve active `audit_uuid` and
  `strategy` filters.

Possible additional hardening:

```text
test_actionplan_cancel_pending_cancels_actions
```

## Data Model API

Current REST behavior in `watcher/api/controllers/v1/data_model.py`:

- `GET /v1/data_model` defaults to `data_model_type='compute'`.
- `GET /v1/data_model?data_model_type=compute` is supported.
- `audit_uuid` can be passed to filter by audit scope.
- There is no `detail=True` parameter.
- The API parameter is `data_model_type`, not `type`.

Interpretation:

- The no-filter timeout noted in the task is not caused by a missing REST
  default in Epoxy: the REST default is already `compute`.
- If OSC times out without a type, inspect watcherclient/OSC behavior before
  changing the backend contract.
- For Horizon compatibility, prefer calling:

```http
GET /v1/data_model?data_model_type=compute
GET /v1/data_model?data_model_type=compute&audit_uuid=<uuid>
```

Useful tests to add:

```text
test_get_all_default_compute
test_get_all_with_audit_uuid
test_get_all_invalid_data_model_type
```

## Services, Scoring Engines, Strategies

Services already have list/detail/get tests, pagination tests, sort-key tests,
and policy tests in `watcher/tests/api/v1/test_services.py`.

Before adding behavior, inspect existing controller support and avoid inventing
new parameters where the API already has a convention.

Minimum useful hardening:

- Verify scoring engine list supports/validates `limit`, `marker`, `sort_key`,
  `sort_dir` if the controller exposes them.
- Verify `GET /v1/strategies/<strategy>/state` has a direct API test.

## Recommended Work Order

### Phase 0: Align Specs With Epoxy

Update local task docs so they reference actual Epoxy paths and parameter names:

- singular controller filenames;
- tests under `watcher/tests/api/v1/`;
- action plan filter name `audit_uuid`;
- data model parameter names `data_model_type` and `audit_uuid`;
- `audit_template_uuid` filter marked as schema-changing or deferred.

### Phase 1: Low-Risk Backend Patch

Implement audit `state` list filter only.

Files likely touched:

```text
watcher/api/controllers/v1/audit.py
watcher/tests/api/v1/test_audits.py
api-ref/source/watcher-api-v1-audits.inc
api-ref/source/parameters.yaml
releasenotes/notes/<new-note>.yaml
```

Run:

```bash
tox -e py3 -- watcher.tests.api.v1.test_audits
tox -e pep8
```

### Phase 2: Regression Coverage Without Contract Expansion

Add tests for existing behavior that Horizon depends on:

- `EVENT` audit create;
- audit rename PATCH;
- action plan list with `audit_uuid + limit + sort`;
- data model default compute and `audit_uuid`.

### Phase 3: Contract Decisions

Decide separately:

- whether to reject `force=True` for `CONTINUOUS` at backend level;
- whether `audit_template_uuid` filtering is mandatory enough to justify a DB
  schema migration and object-version update;
- whether to add aliases like `audit` or `type`, or keep existing Epoxy API
  names and adapt Horizon wrapper code.

## Watcher vs Masakari Boundary

Do not implement Masakari HA concepts in Watcher:

- no fencing;
- no host failure recovery;
- no Nova evacuation workflow;
- no staged start leases;
- no etcd recovery state.

Watcher work should stay in optimization/audit/action-plan/data-model API
scope. Masakari remains the owner for host failure recovery and staged recovery.
