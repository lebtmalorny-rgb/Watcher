# Action Plan Cancel Endpoint Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a microversioned `POST /v1/action_plans/<uuid>/cancel` endpoint for Watcher API `1.5`.

**Architecture:** Reuse the existing PATCH cancel state machine instead of creating a second set of transitions. The new endpoint is a thin controller action with its own policy rule and microversion gate.

**Tech Stack:** Watcher Pecan/WSME API controller, oslo.policy, stestr functional tests, OpenStack API microversions.

**Status note:** This P2.1 plan was completed with API `1.5`. Later P2.2 work
raises the branch maximum microversion beyond this plan.

---

### Task 1: README and design traceability

**Files:**
- Create: `docs/specs/README_WATCHER_HORIZON_GOAL.md`
- Modify: `docs/specs/CODEX_WATCHER_P2_API_EXTENSIONS.md`

- [x] **Step 1: Record the overall goal**

Write a separate README that states the backend goal: prepare Watcher Epoxy
2025.1 for a future Horizon Watcher plugin while keeping old API clients
compatible.

- [x] **Step 2: Keep P2 scope unchanged**

Confirm P2 still starts with action plan cancel endpoint and keeps
`audit_template_uuid` response and data model `detail` for later tasks.

### Task 2: RED tests for cancel endpoint

**Files:**
- Modify: `watcher/tests/api/v1/test_actions_plans.py`
- Modify: `watcher/tests/api/v1/test_microversions.py`

- [x] **Step 1: Add endpoint behavior tests**

Add tests for:

```text
POST /v1/action_plans/<uuid>/cancel
OpenStack-API-Version: infra-optim 1.5
```

The tests must cover `PENDING -> CANCELLED`, `RECOMMENDED -> CANCELLED`,
`ONGOING -> CANCELLING`, invalid source state, not found, policy denied, and
pre-`1.5` compatibility.

- [x] **Step 2: Add version discovery test**

Assert that `versions.max_version_string()` becomes `1.5` after the feature.

- [x] **Step 3: Run RED**

Run:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.api.v1.test_actions_plans.TestCancelActionPlan watcher.tests.api.v1.test_microversions.TestMicroversions.test_latest_microversion
```

Expected before implementation: failures caused by unsupported version or
missing `cancel` action.

### Task 3: Implement endpoint and microversion

**Files:**
- Modify: `watcher/api/controllers/v1/versions.py`
- Modify: `watcher/api/controllers/v1/utils.py`
- Modify: `watcher/api/controllers/v1/action_plan.py`
- Modify: `watcher/common/policies/action_plan.py`
- Modify: `watcher/tests/fake_policy.py`

- [x] **Step 1: Add API version 1.5**

Add enum value `MINOR_5_ACTION_PLAN_CANCEL = 5` and make API `1.5` the
maximum supported microversion for the P2.1 change.

- [x] **Step 2: Add microversion helper**

Add `allow_action_plan_cancel()` that returns true for request minor `>= 5`.

- [x] **Step 3: Add policy rule**

Add `action_plan:cancel` with operation
`POST /v1/action_plans/{action_plan_uuid}/cancel`.

- [x] **Step 4: Add controller action**

Register `cancel` in `_custom_actions` and implement `cancel()` so it:

```text
RECOMMENDED -> CANCELLED
PENDING     -> CANCELLED
ONGOING     -> CANCELLING
```

The action must return the normal `ActionPlan` body and must cancel linked
actions only for immediate `CANCELLED`.

### Task 4: Documentation and verification

**Files:**
- Modify: `watcher/api/controllers/rest_api_version_history.rst`
- Modify: `api-ref/source/watcher-api-v1-actionplans.inc`
- Create or reuse: `api-ref/source/samples/actionplan-cancel-response.json`
- Modify: `docs/specs/CODEX_WATCHER_HORIZON_BACKEND_IMPLEMENTATION.md`

- [x] **Step 1: Document API version 1.5**

Add version-history entry for dedicated action plan cancel endpoint.

- [x] **Step 2: Document api-ref endpoint**

Add `POST /v1/action_plans/{actionplan_ident}/cancel` and mark it as
available since API `1.5`.

- [x] **Step 3: Run verification**

Run focused tests, action plan API tests, microversion tests, `py_compile`,
and `git diff --check`.
