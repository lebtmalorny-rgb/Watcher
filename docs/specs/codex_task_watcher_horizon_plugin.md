# Codex Task — Standalone Watcher Horizon plugin for OpenStack Epoxy / 2025.1

## Target repository

Use this task in a **standalone Horizon plugin repository** that will integrate OpenStack Watcher into Horizon.

This task is separate from backend `openstack/watcher` development. The plugin must consume Watcher API behavior and degrade gracefully when some backend filters are not available.

## Product goal

Build a Horizon plugin that reproduces the practical capabilities of:

```bash
openstack optimize ...
```

for Watcher resources, especially audits, audit templates, action plans, actions, goals, strategies, data model, services, and scoring engines.

The most important engineering requirement is a solid **Watcher API client layer with server-side pagination, sorting, filtering, and safe fallbacks**.

## Hard boundaries

1. Modify only this Horizon plugin repository.
2. Do not modify `openstack/watcher`, Horizon core, or `python-watcherclient`.
3. Do not call `openstack optimize ...` from Django/Horizon code.
4. Use `python-watcherclient` or a Keystone-session API client.
5. Keep the plugin compatible with OpenStack Epoxy / 2025.1.
6. Keep all backend-dependent behavior feature-gated or capability-aware.
7. Add unit tests for API wrappers, forms, tables, and actions.
8. Do not implement webhook triggering by default. Hide it behind a feature flag if placeholders are added.

## First steps for Codex

Before editing:

1. Inspect the plugin structure and identify:
   - Horizon dashboard registration files;
   - `enabled/` files;
   - API wrapper modules;
   - tables, forms, workflows, views, urls, templates;
   - tests and fixtures.
2. Identify whether this plugin is based on upstream `watcher-dashboard` or a new package.
3. Reuse Horizon conventions already present in the repository.
4. Produce a concise file-level implementation plan before making changes.

## Feature flags and settings

Add settings or constants similar to the following, using project naming conventions:

```python
WATCHER_ENABLE_WEBHOOKS = False
WATCHER_ENABLE_ADVANCED_PATCH = False
WATCHER_DEFAULT_PAGE_SIZE = 25
WATCHER_MAX_PAGE_SIZE = 100
WATCHER_DEFAULT_DATAMODEL_TYPE = "compute"
```

Add capability detection or conservative fallback settings:

```python
WATCHER_BACKEND_SUPPORTS_AUDIT_STATE_FILTER = False
WATCHER_BACKEND_SUPPORTS_AUDIT_TEMPLATE_FILTER = False
WATCHER_BACKEND_SUPPORTS_DATA_MODEL_DETAIL = False
WATCHER_BACKEND_SUPPORTS_DATA_MODEL_JSON_DETAIL = False
```

If the backend has already been patched to support `state` and `audit_template_uuid` audit filters, these can be enabled in deployment settings. If disabled, the plugin must not send those filters to the API.

## P0: Watcher API wrapper

Implement or extend an internal API module, for example:

```text
<plugin_package>/api/watcher.py
```

Do not expose raw watcherclient calls throughout views/forms. Views should call this wrapper.

### Client initialization

Implement:

```python
def watcherclient(request):
    """Return authenticated Watcher client for the current Horizon request."""
```

Requirements:

- Use the existing Horizon request/session authentication pattern.
- Respect endpoint type, region, interface, and microversion style used by the project.
- Log failures using the project’s logging pattern.
- Convert client exceptions into Horizon-friendly exceptions only at the API/view boundary.

### List options helper

Create a small reusable list option helper if one does not exist:

```python
class WatcherListOptions:
    def __init__(self, limit=None, marker=None, sort_key=None, sort_dir=None,
                 detail=False, filters=None):
        self.limit = limit
        self.marker = marker
        self.sort_key = sort_key
        self.sort_dir = sort_dir
        self.detail = detail
        self.filters = filters or {}
```

Or use a dataclass if the project already uses dataclasses and Python compatibility allows it.

Add helpers:

```python
def clean_params(params):
    """Drop None and empty-string values before calling Watcher."""
```

```python
def get_next_marker(items):
    """Return uuid/id of last item for cursor pagination."""
```

```python
def make_page(items, limit=None, marker=None):
    """Return items plus next_marker/has_next metadata if the project supports it."""
```

Do not add a heavy pagination dependency.

## P0 API method contracts

### Audits

```python
def audit_list(
    request,
    detail=False,
    goal=None,
    strategy=None,
    state=None,
    audit_template_uuid=None,
    limit=None,
    marker=None,
    sort_key=None,
    sort_dir=None,
):
    """List audits with server-side filters when supported."""
```

Behavior:

- Always pass these when provided:
  - `goal`
  - `strategy`
  - `limit`
  - `marker`
  - `sort_key`
  - `sort_dir`
  - `detail`
- Pass `state` only if `WATCHER_BACKEND_SUPPORTS_AUDIT_STATE_FILTER` is true.
- Pass `audit_template_uuid` only if `WATCHER_BACKEND_SUPPORTS_AUDIT_TEMPLATE_FILTER` is true.
- If `state` or `audit_template_uuid` filters are requested but backend support is disabled, return server result with a clear metadata flag that view/table code can use for client-side fallback.
- Never send unsupported query parameters that cause backend HTTP 400.

Recommended metadata shape:

```python
{
    "items": audits,
    "next_marker": next_marker,
    "has_next": has_next,
    "client_side_filters": {
        "state": "PENDING",
        "audit_template_uuid": "..."
    }
}
```

If the project already has a pagination object, adapt this behavior to it.

```python
def audit_get(request, audit_id):
    """Show one audit."""
```

```python
def audit_create(
    request,
    audit_template_uuid,
    audit_type="ONESHOT",
    name=None,
    parameters=None,
    interval=None,
    auto_trigger=False,
    start_time=None,
    end_time=None,
    force=False,
):
    """Create audit with OSC parity."""
```

Required create behavior:

| Field | Plugin behavior |
|---|---|
| `audit_template_uuid` | Required unless existing backend/client explicitly supports another path. Resolve names to UUID outside this wrapper if needed. |
| `audit_type` | Allow `ONESHOT`, `CONTINUOUS`, `EVENT`. |
| `parameters` | Accept a Python dict. Parse/validate JSON in forms before calling the wrapper. |
| `interval` | Top-level field. Do not place it inside `parameters`. Required for `CONTINUOUS`. |
| `auto_trigger` | Top-level boolean. |
| `start_time` | Pass through when provided. Use backend/OSC-compatible format. |
| `end_time` | Pass through when provided. Use backend/OSC-compatible format. |
| `force` | Pass for non-`CONTINUOUS` audits only. If `audit_type == CONTINUOUS` and `force` is true, raise a validation error before API call. |
| `EVENT` | Allow create, but do not assume webhook trigger support. |

```python
def audit_update(request, audit_id, op, values):
    """Generic JSON PATCH wrapper for audits."""
```

Safe convenience wrappers:

```python
def audit_rename(request, audit_id, name):
    return audit_update(request, audit_id, "replace", {"name": name})
```

```python
def audit_cancel(request, audit_id):
    return audit_update(request, audit_id, "replace", {"state": "CANCELLED"})
```

```python
def audit_delete(request, audit_id):
    """Delete audit if backend state allows it."""
```

### Audit templates

```python
def audittemplate_list(
    request,
    detail=False,
    goal=None,
    strategy=None,
    limit=None,
    marker=None,
    sort_key=None,
    sort_dir=None,
):
    """List audit templates with filters/pagination."""
```

```python
def audittemplate_get(request, template_id):
    """Show one audit template."""
```

```python
def audittemplate_create(request, name, goal, strategy=None, description=None, scope=None):
    """Create audit template."""
```

```python
def audittemplate_update(request, template_id, op, values):
    """Patch audit template fields: name, description, scope, etc."""
```

```python
def audittemplate_delete(request, template_id):
    """Delete audit template."""
```

### Action plans

```python
def actionplan_list(
    request,
    audit=None,
    detail=False,
    limit=None,
    marker=None,
    sort_key=None,
    sort_dir=None,
):
    """List action plans with server-side pagination/sorting."""
```

```python
def actionplan_get(request, actionplan_id):
    """Show one action plan."""
```

```python
def actionplan_start(request, actionplan_id):
    """Start an action plan."""
```

```python
def actionplan_update(request, actionplan_id, op, values):
    """Generic JSON PATCH wrapper for action plans."""
```

```python
def actionplan_cancel(request, actionplan_id, current_state=None):
    """Cancel action plan using backend-supported state transition."""
```

Cancel behavior:

- Prefer existing watcherclient cancel method if available.
- Otherwise use PATCH.
- If `current_state == "ONGOING"`, use `CANCELLING` if required by backend semantics.
- If `current_state == "PENDING"`, use `CANCELLED`.
- If state is unknown, use the backend-supported cancel command or default PATCH expected by existing client behavior.
- Do not make the UI construct raw patch documents for normal cancel.

```python
def actionplan_delete(request, actionplan_id):
    """Delete/archive action plan if backend state allows it."""
```

### Actions

```python
def action_list(
    request,
    action_plan=None,
    audit=None,
    detail=False,
    limit=None,
    marker=None,
    sort_key=None,
    sort_dir=None,
):
    """List actions with filters/pagination."""
```

```python
def action_get(request, action_id):
    """Show one action."""
```

```python
def action_update(request, action_id, op, values):
    """Optional PATCH wrapper for action skip/update if supported."""
```

Do not implement action delete/start UI unless explicitly required later.

### Goals and strategies

```python
def goal_list(request, detail=False, limit=None, marker=None, sort_key=None, sort_dir=None):
    """List goals."""
```

```python
def goal_get(request, goal_id):
    """Show one goal."""
```

```python
def strategy_list(request, goal=None, detail=False, limit=None, marker=None, sort_key=None, sort_dir=None):
    """List strategies, optionally filtered by goal."""
```

```python
def strategy_get(request, strategy_id):
    """Show one strategy."""
```

```python
def strategy_state(request, strategy_name):
    """Return strategy requirements/state for diagnostics and create forms."""
```

### Data model

```python
def datamodel_list(request, model_type="compute", audit=None, detail=False,
                   detail_format=None):
    """List Watcher CDM data."""
```

Required behavior:

- Default `model_type` must be `compute`.
- Send backend query parameter `data_model_type=compute` by default.
- `detail=true` must be explicit and requires backend API `>= 1.7`.
- `detail_format=json` must be explicit and requires backend API `>= 1.8`.
- `audit_uuid` may be passed when user wants the model scoped to a specific
  audit.
- When `detail=true` is used without `detail_format=json`, backend `context`
  is an XML string.
- When `detail=true&detail_format=json` is used and a data model is
  available, backend `context` is a JSON object.
- For any detail format, `context == []` means the backend has no
  scoped/latest data model available.
- If the backend call times out or returns too much data, show a Horizon-friendly error and preserve page usability.

### Services

```python
def service_list(request, detail=False, limit=None, marker=None, sort_key=None, sort_dir=None):
    """List Watcher services for health views."""
```

```python
def service_get(request, service_id):
    """Show one Watcher service."""
```

### Scoring engines

```python
def scoringengine_list(request, detail=False, limit=None, marker=None, sort_key=None, sort_dir=None):
    """List scoring engines."""
```

```python
def scoringengine_get(request, scoringengine_id):
    """Show one scoring engine."""
```

## P0: pagination contract for Horizon tables

Implement a consistent cursor pagination contract for all Watcher list tables.

### Request parameters from table/view to API wrapper

Every list view should be able to pass:

```text
limit
marker
sort_key
sort_dir
filters
detail
```

### Marker handling

- Use the UUID/id of the last item as `next_marker` when backend does not return an explicit next marker.
- `has_next` can be approximated as `len(items) >= limit` when no explicit total/next link exists.
- Do not promise total counts unless backend returns them.
- Maintain previous-page marker stack in the view/session if the existing Horizon table component requires it.

### Sorting

- Expose only safe sort keys per resource.
- Do not send arbitrary user-provided sort keys directly to Watcher.
- Map UI column keys to backend sort keys explicitly.

Recommended initial sort keys:

```python
AUDIT_SORT_KEYS = {"uuid", "name", "state", "audit_type", "created_at", "updated_at", "start_time", "end_time"}
ACTIONPLAN_SORT_KEYS = {"uuid", "state", "created_at", "updated_at"}
AUDIT_TEMPLATE_SORT_KEYS = {"uuid", "name", "created_at", "updated_at"}
ACTION_SORT_KEYS = {"uuid", "state", "action_type", "created_at", "updated_at"}
GOAL_SORT_KEYS = {"uuid", "name", "display_name"}
STRATEGY_SORT_KEYS = {"uuid", "name", "display_name"}
SERVICE_SORT_KEYS = {"id", "name", "host", "status", "updated_at"}
SCORINGENGINE_SORT_KEYS = {"uuid", "name", "created_at", "updated_at"}
```

Adjust to actual backend fields after inspecting object schemas.

### Filters

Audits:

| UI filter | Server behavior |
|---|---|
| `goal` | Send to backend. |
| `strategy` | Send to backend. |
| `state` | Send only if backend capability is enabled; otherwise client-side fallback. |
| `audit_template_uuid` | Send only if backend capability is enabled; otherwise client-side fallback. |
| `type` / `audit_type` | Send only if backend supports it; otherwise client-side fallback. |

Audit templates:

| UI filter | Server behavior |
|---|---|
| `goal` | Send to backend if supported. |
| `strategy` | Send to backend if supported. |

Action plans:

| UI filter | Server behavior |
|---|---|
| `audit` | Send to backend. |
| `state` | Send only if backend supports it. |

Actions:

| UI filter | Server behavior |
|---|---|
| `action_plan` | Send to backend if supported. |
| `audit` | Send to backend if supported. |
| `state` | Send only if backend supports it. |

Data model:

| UI filter | Server behavior |
|---|---|
| `type` | Always send; default `compute`. |
| `audit` | Send when provided. |
| `detail` | Send only when user explicitly asks. |

## P1: Horizon panels and pages

Implement panels in this order.

### 1. Audits panel

Features:

- server-side `goal` and `strategy` filters;
- optional/capability-aware `state` and `audit_template` filters;
- sort and cursor pagination;
- create audit action;
- show audit details;
- rename audit;
- cancel audit using `audit_cancel` wrapper;
- delete audit only when backend state allows it.

Columns:

```text
Name
UUID
State
Type
Audit Template
Goal
Strategy
Interval
Next run
Auto trigger
Force
Created
Updated
Status message
```

Create Audit form:

- audit template selector;
- audit type: `ONESHOT`, `CONTINUOUS`, `EVENT`;
- name;
- parameters JSON/form field;
- interval top-level field;
- auto trigger;
- start time;
- end time;
- force for non-`CONTINUOUS` only.

Validation:

- `CONTINUOUS` requires interval.
- `force` is disabled/rejected for `CONTINUOUS`.
- parameters must be valid JSON object before wrapper call.
- interval must not be merged into parameters.
- `EVENT` create is allowed, but webhook trigger UI remains hidden unless enabled.

### 2. Audit Templates panel

Features:

- list/show/create/update/delete;
- filters by goal and strategy;
- pagination and sorting;
- scope editor.

Scope editor P0:

- raw YAML/JSON textarea;
- validation before submit;
- formatted preview.

Scope editor P1:

- structured builder for compute/storage scopes;
- chips for availability zones, aggregates, excluded nodes, volumes, projects;
- raw mode remains available.

### 3. Action Plans panel

Features:

- list/show;
- filter by audit;
- pagination and sorting;
- start;
- cancel;
- delete/archive in allowed states;
- action timeline on detail page.

State-aware actions:

- show `Start` only when backend state allows start;
- show `Cancel` for pending/ongoing plans;
- show `Delete/Archive` only for terminal or backend-allowed states.

### 4. Actions panel

Features:

- list/show;
- filters by action plan and audit where supported;
- pagination and sorting;
- optional update/skip action if backend/client supports PATCH.

Do not add destructive actions unless explicitly required.

### 5. Goals panel

Features:

- read-only list/show;
- pagination and sorting;
- link to strategies and templates for the selected goal.

### 6. Strategies panel

Features:

- read-only list/show;
- filter by goal;
- pagination and sorting;
- `Strategy State` / requirements tab from `strategy_state(request, strategy_name)`.

Strategy State display fields:

```text
Type
State
Mandatory
Comment
```

Use this data in create forms to warn when required datasource, metrics, or CDM are unavailable.

### 7. Data Model panel

Features:

- default `data_model_type=compute`;
- optional audit filter;
- explicit `detail` switch;
- compact JSON view and optional raw XML detail view;
- safe timeout/error handling.

Do not load all datamodel types by default.

### 8. Services panel

Features:

- read-only list/show;
- health badges for decision engine, applier, API, or actual service types returned by backend;
- pagination and sorting where supported.

### 9. Scoring Engines panel

Features:

- read-only list/show;
- pagination and sorting where supported.

### 10. Webhooks placeholder

Do not enable by default.

If adding a placeholder:

```python
if settings.WATCHER_ENABLE_WEBHOOKS:
    # show endpoint/test trigger UI
else:
    # hide completely
```

## Error handling

Use Horizon-friendly messages.

Examples:

- Backend does not support a requested server-side filter:
  - do not send the filter;
  - apply client-side fallback only for current page if unavoidable;
  - show a small note in debug/admin mode, not a user-facing error for normal operators.
- Datamodel timeout:
  - show a clear message asking user to narrow type/audit/detail;
  - do not break the entire dashboard.
- Invalid JSON parameters:
  - validate in form;
  - do not call Watcher.
- Invalid state transition:
  - show backend message in Horizon toast/error area.

## Tests to implement

### API wrapper tests

1. `test_audit_list_passes_goal_strategy_limit_marker_sort`
2. `test_audit_list_does_not_send_state_when_backend_filter_disabled`
3. `test_audit_list_sends_state_when_backend_filter_enabled`
4. `test_audit_list_does_not_send_audit_template_uuid_when_filter_disabled`
5. `test_audit_create_continuous_payload_contains_top_level_interval`
6. `test_audit_create_continuous_payload_contains_start_end_auto_trigger`
7. `test_audit_create_continuous_rejects_force`
8. `test_audit_create_oneshot_allows_force`
9. `test_audit_create_event_type_allowed`
10. `test_audit_update_rename_patch_payload`
11. `test_audit_cancel_patch_payload`
12. `test_actionplan_list_passes_audit_limit_marker_sort`
13. `test_actionplan_cancel_uses_patch_or_client_cancel`
14. `test_datamodel_list_defaults_to_compute`
15. `test_strategy_state_calls_expected_client_method`
16. `test_service_list_passes_pagination`
17. `test_scoringengine_list_passes_pagination`

### Form tests

1. `test_create_audit_form_continuous_requires_interval`
2. `test_create_audit_form_continuous_disables_force`
3. `test_create_audit_form_accepts_event`
4. `test_create_audit_form_parameters_must_be_json_object`
5. `test_create_audit_form_interval_not_in_parameters`
6. `test_create_audit_form_start_end_time_format`

### Table/view tests

1. `test_audits_table_uses_server_side_goal_filter`
2. `test_audits_table_uses_server_side_strategy_filter`
3. `test_audits_table_uses_cursor_marker_for_next_page`
4. `test_audits_table_sort_key_mapping`
5. `test_actionplans_table_cancel_action_visible_for_pending_or_ongoing`
6. `test_datamodel_view_sends_type_compute_by_default`

Use the repository’s existing test naming and mocking patterns.

## Manual validation checklist

After deploying plugin against a test OpenStack cloud:

```bash
# CLI reference behavior
openstack optimize audit list --goal server_consolidation --limit 2
openstack optimize audit list --strategy basic --sort-key name --sort-dir desc
openstack optimize audit list --limit 2 --marker <audit_uuid>

openstack optimize audit create \
  -t CONTINUOUS \
  -i 60 \
  --start-time '2026-12-31 23:00:00' \
  --end-time '2027-06-30 23:00:00' \
  --auto-trigger \
  -a <audit_template> \
  --name ui-regression-continuous

openstack optimize audit create \
  -t ONESHOT \
  --force \
  -a <audit_template> \
  --name ui-regression-force

openstack optimize audit create \
  -t EVENT \
  -a <audit_template> \
  --name ui-regression-event

openstack optimize datamodel list --type compute
openstack optimize service list
openstack optimize strategy state <strategy_name>
```

Then verify the same flows in Horizon:

1. Audits list opens without loading all audits.
2. Goal and strategy filters call backend with query params.
3. Pagination uses `limit` and `marker`.
4. Sorting uses `sort_key` and `sort_dir`.
5. Create CONTINUOUS audit sends interval as top-level field.
6. Create CONTINUOUS audit sends start/end time and auto trigger.
7. Force is not available for CONTINUOUS.
8. Create ONESHOT audit can send force.
9. EVENT audit type is selectable.
10. Action plan cancel works from row action.
11. Datamodel panel defaults to compute.
12. Services and strategy state pages show diagnostic data.

## Suggested implementation phases

### Phase 1 — API/pagination foundation

- Add/extend `api/watcher.py`.
- Add pagination helper and safe sort key mappings.
- Add API wrapper tests.
- No major UI changes yet.

### Phase 2 — Audits and Action Plans P0 UI

- Audits table with server-side goal/strategy filters.
- Cursor pagination.
- Create Audit form fields.
- Audit rename/cancel wrappers.
- Action Plan cancel row action.

### Phase 3 — Read-only diagnostic panels

- Data Model.
- Services.
- Scoring Engines.
- Strategy State.

### Phase 4 — Audit Template scope editor and advanced polish

- Better scope editor.
- Action timeline.
- Advanced PATCH modal behind setting.
- Optional webhook placeholder behind setting.

## Validation commands

Run the plugin’s normal checks. At minimum:

```bash
tox -e py3
tox -e pep8
```

If the project has JavaScript/static checks, run them too.

## Definition of done

The plugin task is complete when:

1. A single internal Watcher API wrapper is used by all Watcher views/forms/tables.
2. Audits, audit templates, action plans, actions, goals, strategies, data model, services, and scoring engines have wrapper methods.
3. List views use `limit`, `marker`, `sort_key`, and `sort_dir` where backend supports them.
4. Unsupported filters are not sent to backend unless a capability flag enables them.
5. Create Audit supports `EVENT`, `start_time`, `end_time`, `force`, `parameters`, `interval`, and `auto_trigger` with correct validation.
6. `interval` is never sent inside `parameters` for continuous audits.
7. `force` is rejected or hidden for continuous audits.
8. Action Plan cancel/update wrappers exist and are used by row actions.
9. Data Model defaults to `compute` and does not load all types by default.
10. Tests cover API payloads, filters, pagination, form validation, and action visibility.
11. `tox -e py3` and `tox -e pep8` pass or unrelated failures are clearly documented.
12. Final Codex response includes changed files, tests run, and remaining TODOs.

## Out of scope

- Watcher backend changes.
- New Watcher API microversions.
- Webhook trigger execution.
- Replacing Horizon with a new frontend stack.
- Running `openstack` CLI from Django code.
