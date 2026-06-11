# Audit Template Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persisted audit-to-audit-template relationship and expose a backward-compatible `audit_template_uuid` server-side filter on audit collection APIs.

**Architecture:** Store the relationship as nullable `audits.audit_template_id`, map it through SQLAlchemy and `objects.Audit`, and filter through `_add_audits_filters()` using the existing relationship-filter pattern. Keep audit response bodies unchanged; the new value is internal and used for create/list/filter behavior.

**Tech Stack:** Python, WSME/Pecan API controllers, oslo.versionedobjects, SQLAlchemy, Alembic, stestr, Sphinx api-ref, Reno release notes.

---

## Execution Notes

Use the repository worktree at:

```bash
/Users/dmitry/Desktop/DRS:HA_fork/watcher
```

Use the colon-free test mirror for stestr runs:

```bash
/private/tmp/watcher-src-no-colon
```

Use the prepared virtualenv:

```bash
/private/tmp/watcher-venv-py312
```

After every source change that must be tested, sync the changed files into the
test mirror before running `stestr`. Example:

```bash
rsync -a --exclude=__pycache__ watcher/tests/api/v1/test_audits.py /private/tmp/watcher-src-no-colon/watcher/tests/api/v1/test_audits.py
```

Use this stestr pattern:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run <test-id>
```

Do not commit `.serena/`.

---

## File Structure

Modify:

- `watcher/tests/db/utils.py` - include `audit_template_id` in test audit fixtures.
- `watcher/tests/db/test_audit.py` - DB regression tests for persisted template relationship and combined filters.
- `watcher/db/sqlalchemy/models.py` - add `Audit.audit_template_id` and relationship.
- `watcher/db/sqlalchemy/alembic/versions/c2f4b8d6e3a1_add_audit_template_id_to_audits.py` - schema migration.
- `watcher/objects/audit.py` - add nullable `audit_template_id` object field and bump `VERSION`.
- `watcher/db/sqlalchemy/api.py` - add `audit_template_uuid` filter to `_add_audits_filters()`.
- `watcher/tests/api/v1/test_audits.py` - API regression tests for create persistence, list/detail filters, and pagination links.
- `watcher/api/controllers/v1/audit.py` - wire create persistence and list/detail query params.
- `api-ref/source/parameters.yaml` - document `r_audit_template_uuid`.
- `api-ref/source/watcher-api-v1-audits.inc` - add the parameter to audit list and detail docs.
- `docs/WATCHER_EPOXY_2025_1_ANALYSIS.md` - update implementation status.
- `docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md` - update Horizon integration contract.
- `releasenotes/notes/audit-template-filter-4f65d2cb0dfd13f2.yaml` - release note.

No new API response sample fields are added.

---

### Task 1: RED DB Tests For Audit Template Relationship

**Files:**
- Modify: `watcher/tests/db/utils.py`
- Modify: `watcher/tests/db/test_audit.py`

- [ ] **Step 1: Add `audit_template_id` to DB test audit fixture**

In `watcher/tests/db/utils.py`, update `get_test_audit()` so the `audit_data`
dict includes `audit_template_id` after `goal_id`:

```python
        'goal_id': kwargs.get('goal_id', 1),
        'audit_template_id': kwargs.get('audit_template_id', None),
        'strategy_id': kwargs.get('strategy_id', None),
```

- [ ] **Step 2: Add DB filter tests**

In `watcher/tests/db/test_audit.py`, add this method to `DbAuditTestCase` after
`test_get_audit_list_with_goal_strategy_and_state_filters`:

```python
    def test_get_audit_list_with_audit_template_filter(self):
        goal = utils.create_test_goal(
            id=2, uuid=w_utils.generate_uuid(), name='TEMPLATE_GOAL')
        strategy = utils.create_test_strategy(
            id=2, uuid=w_utils.generate_uuid(), name='TEMPLATE_STRATEGY',
            goal_id=goal.id)
        audit_template = utils.create_test_audit_template(
            id=2, uuid=w_utils.generate_uuid(), name='TEMPLATE_1',
            goal_id=goal.id, strategy_id=strategy.id)
        other_template = utils.create_test_audit_template(
            id=3, uuid=w_utils.generate_uuid(), name='TEMPLATE_2',
            goal_id=goal.id, strategy_id=strategy.id)

        audit1 = utils.create_test_audit(
            id=20, uuid=w_utils.generate_uuid(), name='Template Audit 1',
            goal_id=goal.id, strategy_id=strategy.id,
            audit_template_id=audit_template.id,
            state=objects.audit.State.PENDING)
        audit2 = utils.create_test_audit(
            id=21, uuid=w_utils.generate_uuid(), name='Template Audit 2',
            goal_id=goal.id, strategy_id=strategy.id,
            audit_template_id=audit_template.id,
            state=objects.audit.State.SUCCEEDED)
        utils.create_test_audit(
            id=22, uuid=w_utils.generate_uuid(), name='Other Template Audit',
            goal_id=goal.id, strategy_id=strategy.id,
            audit_template_id=other_template.id,
            state=objects.audit.State.PENDING)
        utils.create_test_audit(
            id=23, uuid=w_utils.generate_uuid(), name='No Template Audit',
            goal_id=goal.id, strategy_id=strategy.id,
            state=objects.audit.State.PENDING)

        res = self.dbapi.get_audit_list(
            self.context,
            filters={'audit_template_uuid': audit_template.uuid})

        self.assertEqual(
            sorted([audit1['id'], audit2['id']]),
            sorted([r.id for r in res]))

    def test_get_audit_list_with_audit_template_and_related_filters(self):
        goal = utils.create_test_goal(
            id=2, uuid=w_utils.generate_uuid(), name='TEMPLATE_GOAL')
        strategy = utils.create_test_strategy(
            id=2, uuid=w_utils.generate_uuid(), name='TEMPLATE_STRATEGY',
            goal_id=goal.id)
        other_strategy = utils.create_test_strategy(
            id=3, uuid=w_utils.generate_uuid(), name='OTHER_TEMPLATE_STRATEGY',
            goal_id=goal.id)
        audit_template = utils.create_test_audit_template(
            id=2, uuid=w_utils.generate_uuid(), name='TEMPLATE_1',
            goal_id=goal.id, strategy_id=strategy.id)
        other_template = utils.create_test_audit_template(
            id=3, uuid=w_utils.generate_uuid(), name='TEMPLATE_2',
            goal_id=goal.id, strategy_id=strategy.id)

        audit1 = utils.create_test_audit(
            id=30, uuid=w_utils.generate_uuid(), name='Matching Audit',
            goal_id=goal.id, strategy_id=strategy.id,
            audit_template_id=audit_template.id,
            state=objects.audit.State.PENDING)
        utils.create_test_audit(
            id=31, uuid=w_utils.generate_uuid(), name='Wrong State Audit',
            goal_id=goal.id, strategy_id=strategy.id,
            audit_template_id=audit_template.id,
            state=objects.audit.State.SUCCEEDED)
        utils.create_test_audit(
            id=32, uuid=w_utils.generate_uuid(), name='Wrong Strategy Audit',
            goal_id=goal.id, strategy_id=other_strategy.id,
            audit_template_id=audit_template.id,
            state=objects.audit.State.PENDING)
        utils.create_test_audit(
            id=33, uuid=w_utils.generate_uuid(), name='Wrong Template Audit',
            goal_id=goal.id, strategy_id=strategy.id,
            audit_template_id=other_template.id,
            state=objects.audit.State.PENDING)

        res = self.dbapi.get_audit_list(
            self.context,
            filters={'audit_template_uuid': audit_template.uuid,
                     'goal_uuid': goal.uuid,
                     'strategy_uuid': strategy.uuid,
                     'state': objects.audit.State.PENDING})

        self.assertEqual([audit1['id']], [r.id for r in res])
```

- [ ] **Step 3: Sync DB test files into test mirror**

Run:

```bash
rsync -a --exclude=__pycache__ watcher/tests/db/utils.py /private/tmp/watcher-src-no-colon/watcher/tests/db/utils.py
rsync -a --exclude=__pycache__ watcher/tests/db/test_audit.py /private/tmp/watcher-src-no-colon/watcher/tests/db/test_audit.py
```

- [ ] **Step 4: Run RED DB tests**

Run:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.db.test_audit.DbAuditTestCase.test_get_audit_list_with_audit_template_filter watcher.tests.db.test_audit.DbAuditTestCase.test_get_audit_list_with_audit_template_and_related_filters
```

Expected: FAIL before implementation. Acceptable failure examples are:

```text
TypeError: 'audit_template_id' is an invalid keyword argument for Audit
```

or an empty result from the unsupported `audit_template_uuid` filter.

Do not continue unless the tests fail for missing model/filter behavior.

---

### Task 2: Implement Data Model, Migration, Object Field, DB Filter

**Files:**
- Modify: `watcher/db/sqlalchemy/models.py`
- Create: `watcher/db/sqlalchemy/alembic/versions/c2f4b8d6e3a1_add_audit_template_id_to_audits.py`
- Modify: `watcher/objects/audit.py`
- Modify: `watcher/db/sqlalchemy/api.py`

- [ ] **Step 1: Add SQLAlchemy column and relationship**

In `watcher/db/sqlalchemy/models.py`, update `class Audit` by adding
`audit_template_id` after `goal_id`, and add the relationship after `goal`:

```python
    goal_id = Column(Integer, ForeignKey('goals.id'), nullable=False)
    audit_template_id = Column(
        Integer, ForeignKey('audit_templates.id'), nullable=True)
    strategy_id = Column(Integer, ForeignKey('strategies.id'), nullable=True)
```

```python
    goal = orm.relationship(Goal, foreign_keys=goal_id, lazy=None)
    audit_template = orm.relationship(
        AuditTemplate, foreign_keys=audit_template_id, lazy=None)
    strategy = orm.relationship(Strategy, foreign_keys=strategy_id, lazy=None)
```

- [ ] **Step 2: Add Alembic migration**

Create
`watcher/db/sqlalchemy/alembic/versions/c2f4b8d6e3a1_add_audit_template_id_to_audits.py`
with:

```python
"""add audit_template_id to audits

Revision ID: c2f4b8d6e3a1
Revises: 609bec748f2a
Create Date: 2026-06-11 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c2f4b8d6e3a1'
down_revision = '609bec748f2a'


def upgrade():
    op.add_column(
        'audits',
        sa.Column('audit_template_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_audits_audit_template_id',
        'audits',
        'audit_templates',
        ['audit_template_id'],
        ['id'])


def downgrade():
    op.drop_constraint(
        'fk_audits_audit_template_id',
        'audits',
        type_='foreignkey')
    op.drop_column('audits', 'audit_template_id')
```

If SQLite migration verification rejects `op.create_foreign_key`, use
Alembic batch operations in this same migration:

```python
def upgrade():
    with op.batch_alter_table('audits') as batch_op:
        batch_op.add_column(
            sa.Column('audit_template_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_audits_audit_template_id',
            'audit_templates',
            ['audit_template_id'],
            ['id'])


def downgrade():
    with op.batch_alter_table('audits') as batch_op:
        batch_op.drop_constraint(
            'fk_audits_audit_template_id',
            type_='foreignkey')
        batch_op.drop_column('audit_template_id')
```

- [ ] **Step 3: Add `audit_template_id` to Audit object**

In `watcher/objects/audit.py`, update the version comment and `VERSION`:

```python
    # Version 1.7: Added 'force' boolean field
    # Version 1.8: Added 'audit_template_id' field
    VERSION = '1.8'
```

Add the field after `goal_id`:

```python
        'goal_id': wfields.IntegerField(),
        'audit_template_id': wfields.IntegerField(nullable=True),
        'strategy_id': wfields.IntegerField(nullable=True),
```

Do not add `audit_template` to `object_fields` in this task.

- [ ] **Step 4: Add `audit_template_uuid` DB filter**

In `watcher/db/sqlalchemy/api.py`, update `_add_audits_filters()` related map:

```python
        related_fieldmap = {
            'goal_uuid': (models.Audit.goal, models.Goal, "uuid"),
            'goal_name': (models.Audit.goal, models.Goal, "name"),
            'audit_template_uuid': (
                models.Audit.audit_template, models.AuditTemplate, "uuid"),
            'strategy_uuid': (
                models.Audit.strategy, models.Strategy, "uuid"),
            'strategy_name': (
                models.Audit.strategy, models.Strategy, "name"),
        }
```

- [ ] **Step 5: Sync implementation files into test mirror**

Run:

```bash
rsync -a --exclude=__pycache__ watcher/db/sqlalchemy/models.py /private/tmp/watcher-src-no-colon/watcher/db/sqlalchemy/models.py
rsync -a --exclude=__pycache__ watcher/db/sqlalchemy/api.py /private/tmp/watcher-src-no-colon/watcher/db/sqlalchemy/api.py
rsync -a --exclude=__pycache__ watcher/objects/audit.py /private/tmp/watcher-src-no-colon/watcher/objects/audit.py
rsync -a --exclude=__pycache__ watcher/db/sqlalchemy/alembic/versions/c2f4b8d6e3a1_add_audit_template_id_to_audits.py /private/tmp/watcher-src-no-colon/watcher/db/sqlalchemy/alembic/versions/c2f4b8d6e3a1_add_audit_template_id_to_audits.py
```

- [ ] **Step 6: Run DB tests to verify GREEN**

Run:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.db.test_audit.DbAuditTestCase.test_get_audit_list_with_audit_template_filter watcher.tests.db.test_audit.DbAuditTestCase.test_get_audit_list_with_audit_template_and_related_filters
```

Expected: PASS.

- [ ] **Step 7: Run full DB audit tests**

Run:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.db.test_audit
```

Expected: all tests pass.

- [ ] **Step 8: Commit data model and DB filter**

Run:

```bash
git add watcher/tests/db/utils.py watcher/tests/db/test_audit.py watcher/db/sqlalchemy/models.py watcher/db/sqlalchemy/api.py watcher/objects/audit.py watcher/db/sqlalchemy/alembic/versions/c2f4b8d6e3a1_add_audit_template_id_to_audits.py
git commit -m "Add audit template relationship to audits"
```

---

### Task 3: RED API Tests For Create, List, Detail, Pagination

**Files:**
- Modify: `watcher/tests/api/v1/test_audits.py`

- [ ] **Step 1: Add API list/detail tests**

In `watcher/tests/api/v1/test_audits.py`, add these methods to
`TestListAudit` after `test_many_with_goal_strategy_and_state_filter`:

```python
    def test_many_with_audit_template_filter(self):
        audit_template = obj_utils.create_test_audit_template(
            self.context, id=2, uuid=utils.generate_uuid(),
            name='Template 2')
        other_template = obj_utils.create_test_audit_template(
            self.context, id=3, uuid=utils.generate_uuid(),
            name='Template 3')

        expected_audit = obj_utils.create_test_audit(
            self.context, id=1, uuid=utils.generate_uuid(),
            name='Template Audit', audit_template_id=audit_template.id)
        obj_utils.create_test_audit(
            self.context, id=2, uuid=utils.generate_uuid(),
            name='Other Template Audit',
            audit_template_id=other_template.id)
        obj_utils.create_test_audit(
            self.context, id=3, uuid=utils.generate_uuid(),
            name='No Template Audit')

        response = self.get_json(
            '/audits?audit_template_uuid=%s' % audit_template.uuid)

        self.assertEqual(1, len(response['audits']))
        self.assertEqual(expected_audit.uuid, response['audits'][0]['uuid'])
        self.assertNotIn('audit_template_uuid', response['audits'][0])

    def test_detail_with_audit_template_filter(self):
        audit_template = obj_utils.create_test_audit_template(
            self.context, id=2, uuid=utils.generate_uuid(),
            name='Template 2')
        other_template = obj_utils.create_test_audit_template(
            self.context, id=3, uuid=utils.generate_uuid(),
            name='Template 3')

        expected_audit = obj_utils.create_test_audit(
            self.context, id=1, uuid=utils.generate_uuid(),
            name='Template Audit', audit_template_id=audit_template.id)
        obj_utils.create_test_audit(
            self.context, id=2, uuid=utils.generate_uuid(),
            name='Other Template Audit',
            audit_template_id=other_template.id)

        response = self.get_json(
            '/audits/detail?audit_template_uuid=%s' % audit_template.uuid)

        self.assertEqual(1, len(response['audits']))
        self.assertEqual(expected_audit.uuid, response['audits'][0]['uuid'])
        self.assertNotIn('audit_template_uuid', response['audits'][0])

    def test_many_with_audit_template_goal_strategy_and_state_filter(self):
        goal = obj_utils.create_test_goal(
            self.context, id=2, uuid=utils.generate_uuid(),
            name='TEST_GOAL_2')
        strategy = obj_utils.create_test_strategy(
            self.context, id=2, uuid=utils.generate_uuid(),
            name='TEST_STRATEGY_2', goal_id=goal.id)
        other_strategy = obj_utils.create_test_strategy(
            self.context, id=3, uuid=utils.generate_uuid(),
            name='TEST_STRATEGY_3', goal_id=goal.id)
        audit_template = obj_utils.create_test_audit_template(
            self.context, id=2, uuid=utils.generate_uuid(),
            name='Template 2', goal_id=goal.id, strategy_id=strategy.id)
        other_template = obj_utils.create_test_audit_template(
            self.context, id=3, uuid=utils.generate_uuid(),
            name='Template 3', goal_id=goal.id, strategy_id=strategy.id)

        expected_audit = obj_utils.create_test_audit(
            self.context, id=1, uuid=utils.generate_uuid(),
            name='Matching Audit', goal_id=goal.id, strategy_id=strategy.id,
            audit_template_id=audit_template.id,
            state=objects.audit.State.PENDING)
        obj_utils.create_test_audit(
            self.context, id=2, uuid=utils.generate_uuid(),
            name='Wrong State Audit', goal_id=goal.id,
            strategy_id=strategy.id, audit_template_id=audit_template.id,
            state=objects.audit.State.SUCCEEDED)
        obj_utils.create_test_audit(
            self.context, id=3, uuid=utils.generate_uuid(),
            name='Wrong Strategy Audit', goal_id=goal.id,
            strategy_id=other_strategy.id,
            audit_template_id=audit_template.id,
            state=objects.audit.State.PENDING)
        obj_utils.create_test_audit(
            self.context, id=4, uuid=utils.generate_uuid(),
            name='Wrong Template Audit', goal_id=goal.id,
            strategy_id=strategy.id, audit_template_id=other_template.id,
            state=objects.audit.State.PENDING)

        response = self.get_json(
            '/audits?audit_template_uuid=%s&goal=%s&strategy=%s&state=%s' % (
                audit_template.uuid, goal.uuid, strategy.uuid,
                objects.audit.State.PENDING))

        self.assertEqual(1, len(response['audits']))
        self.assertEqual(expected_audit.uuid, response['audits'][0]['uuid'])

    def test_many_with_audit_template_filter_and_limit_keeps_next_filter(self):
        audit_template = obj_utils.create_test_audit_template(
            self.context, id=2, uuid=utils.generate_uuid(),
            name='Template 2')
        other_template = obj_utils.create_test_audit_template(
            self.context, id=3, uuid=utils.generate_uuid(),
            name='Template 3')

        for id_ in range(1, 4):
            obj_utils.create_test_audit(
                self.context, id=id_, uuid=utils.generate_uuid(),
                name='Template Audit {0}'.format(id_),
                audit_template_id=audit_template.id)
        obj_utils.create_test_audit(
            self.context, id=4, uuid=utils.generate_uuid(),
            name='Other Template Audit',
            audit_template_id=other_template.id)

        response = self.get_json(
            '/audits?audit_template_uuid=%s&limit=2' % audit_template.uuid)

        self.assertEqual(2, len(response['audits']))
        self.assertIn('audit_template_uuid=%s' % audit_template.uuid,
                      response['next'])
        self.assertIn('limit=2', response['next'])
        self.assertIn(response['audits'][-1]['uuid'], response['next'])
```

- [ ] **Step 2: Add API create persistence test**

In `watcher/tests/api/v1/test_audits.py`, add this method to `TestPost` after
`test_create_audit_with_strategy_parameters`:

```python
    @mock.patch.object(deapi.DecisionEngineAPI, 'trigger_audit')
    def test_create_audit_with_audit_template_persists_relationship(
            self, mock_trigger_audit):
        mock_trigger_audit.return_value = mock.ANY
        fake_spec = {
            "properties": {
                "fake1": {
                    "description": "number parameter example",
                    "type": "number",
                    "minimum": 1.0,
                    "maximum": 10.2,
                }
            },
            'required': ['fake1']
        }
        strategy = obj_utils.create_test_strategy(
            self.context, id=4, uuid=utils.generate_uuid(),
            name='persist_strategy', parameters_spec=fake_spec)
        audit_template = obj_utils.create_test_audit_template(
            self.context, id=4, uuid=utils.generate_uuid(),
            name='persist_template', strategy_id=strategy.id)

        audit_dict = api_utils.audit_post_data(parameters={'fake1': 5.5})
        audit_dict['audit_template_uuid'] = audit_template.uuid
        del_keys = ['uuid', 'goal_id', 'strategy_id', 'state', 'interval',
                    'scope', 'next_run_time', 'hostname']
        for k in del_keys:
            del audit_dict[k]

        response = self.post_json('/audits', audit_dict)

        self.assertEqual('application/json', response.content_type)
        self.assertEqual(HTTPStatus.CREATED, response.status_int)
        audit = objects.Audit.get_by_uuid(
            self.context, response.json['uuid'])
        self.assertEqual(audit_template.id, audit.audit_template_id)
        self.assertNotIn('audit_template_uuid', response.json)
```

- [ ] **Step 3: Sync API test file into test mirror**

Run:

```bash
rsync -a --exclude=__pycache__ watcher/tests/api/v1/test_audits.py /private/tmp/watcher-src-no-colon/watcher/tests/api/v1/test_audits.py
```

- [ ] **Step 4: Run RED API tests**

Run:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.api.v1.test_audits.TestListAudit.test_many_with_audit_template_filter watcher.tests.api.v1.test_audits.TestListAudit.test_detail_with_audit_template_filter watcher.tests.api.v1.test_audits.TestListAudit.test_many_with_audit_template_goal_strategy_and_state_filter watcher.tests.api.v1.test_audits.TestListAudit.test_many_with_audit_template_filter_and_limit_keeps_next_filter watcher.tests.api.v1.test_audits.TestPost.test_create_audit_with_audit_template_persists_relationship
```

Expected: FAIL before controller wiring. Acceptable failure examples are
`Unknown argument: audit_template_uuid`, empty audit collections, or
`audit.audit_template_id` remaining `None` after create.

---

### Task 4: Implement Audit API Create And Query Wiring

**Files:**
- Modify: `watcher/api/controllers/v1/audit.py`

- [ ] **Step 1: Preserve `audit_template_id` inside API Audit objects**

In `watcher/api/controllers/v1/audit.py`, update `Audit.__init__()` after the
existing internal `goal_id` / `strategy_id` handling:

```python
        self.fields.append('goal_id')
        self.fields.append('audit_template_id')
        self.fields.append('strategy_id')
        setattr(self, 'audit_template_id', kwargs.get('audit_template_id',
                wtypes.Unset))
```

This keeps `audit_template_id` available in `audit.as_dict()` for persistence
without declaring `audit_template_uuid` as a response field.

- [ ] **Step 2: Store resolved template id in create flow**

In `AuditPostType.as_audit()`, initialize `audit_template_id` before the first
`if self.audit_template_uuid:` block:

```python
        audit_template_id = None
```

Inside the first successful template resolution block, after
`audit_template = objects.AuditTemplate.get(...)`, set:

```python
                audit_template_id = audit_template.id
```

In the default-name branch that currently re-loads the audit template, reuse the
loaded object when possible:

```python
            elif self.audit_template_uuid:
                audit_template = objects.AuditTemplate.get(
                    context, self.audit_template_uuid)
                self.name = "%s-%s" % (audit_template.name,
                                       timeutils.utcnow().isoformat())
```

Keep this branch functionally identical if the existing variable scope makes a
larger cleanup unnecessary.

Add `audit_template_id` to the returned `Audit(...)`:

```python
            goal_id=self.goal,
            audit_template_id=audit_template_id,
            strategy_id=self.strategy,
```

- [ ] **Step 3: Accept and forward `audit_template_uuid` in collection helper**

Change `_get_audits_collection()` signature to:

```python
    def _get_audits_collection(self, marker, limit,
                               sort_key, sort_dir, expand=False,
                               resource_url=None, goal=None,
                               strategy=None, state=None,
                               audit_template_uuid=None):
```

Add filter wiring after goal filtering:

```python
        if audit_template_uuid:
            filters['audit_template_uuid'] = audit_template_uuid
```

Add next-link preservation:

```python
        if audit_template_uuid:
            next_kwargs['audit_template_uuid'] = audit_template_uuid
```

- [ ] **Step 4: Add query parameter to `get_all()`**

Update the `@wsme_pecan.wsexpose` decorator to include one extra `types.uuid`
argument at the end:

```python
    @wsme_pecan.wsexpose(AuditCollection, types.uuid, int, wtypes.text,
                         wtypes.text, wtypes.text, wtypes.text, wtypes.text,
                         types.uuid)
```

Update the method signature:

```python
    def get_all(self, marker=None, limit=None, sort_key='id', sort_dir='asc',
                goal=None, strategy=None, state=None,
                audit_template_uuid=None):
```

Update the docstring:

```python
        :param audit_template_uuid: audit template UUID to filter by
```

Forward the value:

```python
        return self._get_audits_collection(
            marker, limit, sort_key, sort_dir, goal=goal,
            strategy=strategy, state=state,
            audit_template_uuid=audit_template_uuid)
```

- [ ] **Step 5: Add query parameter to `detail()`**

Update the `@wsme_pecan.wsexpose` decorator to include one extra `types.uuid`
argument at the end:

```python
    @wsme_pecan.wsexpose(AuditCollection, wtypes.text, types.uuid, int,
                         wtypes.text, wtypes.text, wtypes.text, types.uuid)
```

Update the method signature:

```python
    def detail(self, goal=None, marker=None, limit=None,
               sort_key='id', sort_dir='asc', state=None,
               audit_template_uuid=None):
```

Update the docstring:

```python
        :param audit_template_uuid: audit template UUID to filter by
```

Forward the value:

```python
        return self._get_audits_collection(
            marker, limit, sort_key, sort_dir, expand, resource_url,
            goal=goal, state=state,
            audit_template_uuid=audit_template_uuid)
```

Do not add `strategy` to `detail()` in this task.

- [ ] **Step 6: Sync API controller into test mirror**

Run:

```bash
rsync -a --exclude=__pycache__ watcher/api/controllers/v1/audit.py /private/tmp/watcher-src-no-colon/watcher/api/controllers/v1/audit.py
```

- [ ] **Step 7: Run API tests to verify GREEN**

Run:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.api.v1.test_audits.TestListAudit.test_many_with_audit_template_filter watcher.tests.api.v1.test_audits.TestListAudit.test_detail_with_audit_template_filter watcher.tests.api.v1.test_audits.TestListAudit.test_many_with_audit_template_goal_strategy_and_state_filter watcher.tests.api.v1.test_audits.TestListAudit.test_many_with_audit_template_filter_and_limit_keeps_next_filter watcher.tests.api.v1.test_audits.TestPost.test_create_audit_with_audit_template_persists_relationship
```

Expected: PASS.

- [ ] **Step 8: Run full audit API tests**

Run:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.api.v1.test_audits
```

Expected: all tests pass.

- [ ] **Step 9: Commit API wiring**

Run:

```bash
git add watcher/tests/api/v1/test_audits.py watcher/api/controllers/v1/audit.py
git commit -m "Add audit template filter API support"
```

---

### Task 5: Documentation, API Reference, Release Note

**Files:**
- Modify: `api-ref/source/parameters.yaml`
- Modify: `api-ref/source/watcher-api-v1-audits.inc`
- Modify: `docs/WATCHER_EPOXY_2025_1_ANALYSIS.md`
- Modify: `docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md`
- Create: `releasenotes/notes/audit-template-filter-4f65d2cb0dfd13f2.yaml`

- [ ] **Step 1: Add api-ref parameter**

In `api-ref/source/parameters.yaml`, add after `r_audit_state`:

```yaml
r_audit_template_uuid:
  description: |
    Optional audit template UUID used for filtering Audit collection results.
    The filter matches audits whose persisted ``audit_template_id`` points to
    the specified Audit Template. Audits created before this relationship was
    stored, or audits created directly from a goal, do not match this filter.
  in: query
  required: false
  type: string
```

- [ ] **Step 2: Add parameter to audit list api-ref**

In `api-ref/source/watcher-api-v1-audits.inc`, add
`audit_template_uuid` to the List Audit request parameters:

```rst
   - audit_template_uuid: r_audit_template_uuid
```

Place it after `state`.

- [ ] **Step 3: Add parameter to audit detail api-ref**

In `api-ref/source/watcher-api-v1-audits.inc`, add
`audit_template_uuid` to the List Audit Detailed request parameters:

```rst
   - audit_template_uuid: r_audit_template_uuid
```

Place it after `state`.

- [ ] **Step 4: Update Horizon integration doc**

In `docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md`, replace the section that
states `GET /v1/audits?audit_template_uuid=<UUID>` is not implemented with:

```markdown
### Audit template filter

`GET /v1/audits?audit_template_uuid=<UUID>` and
`GET /v1/audits/detail?audit_template_uuid=<UUID>` are supported by this
branch.

The backend persists the source audit template as `audits.audit_template_id`
when an audit is created with `audit_template_uuid`. The response body shape is
unchanged: audit list/detail responses still do not expose
`audit_template_uuid`.

Integration notes:

- Horizon may send `audit_template_uuid` when this backend capability is
  deployed.
- The filter matches audits that have a persisted `audit_template_id`.
- Historical audits created before this schema change are not backfilled and do
  not match the filter unless their `audit_template_id` is populated later.
- Audits created directly from `goal` have no audit template relationship and
  do not match the filter.
```

- [ ] **Step 5: Update analysis doc**

In `docs/WATCHER_EPOXY_2025_1_ANALYSIS.md`, update the audit template section
so it states:

```markdown
Implemented on this branch:

- `audits.audit_template_id` stores the source audit template for new audits
  created with `audit_template_uuid`.
- `GET /v1/audits?audit_template_uuid=<uuid>` is a server-side filter.
- `GET /v1/audits/detail?audit_template_uuid=<uuid>` is a server-side filter.
- The response body shape is unchanged; `audit_template_uuid` is not returned
  in audit response bodies.
- Historical audits are not backfilled.
```

Keep the historical upstream/backport notes if they remain useful.

- [ ] **Step 6: Add release note**

Create `releasenotes/notes/audit-template-filter-4f65d2cb0dfd13f2.yaml`:

```yaml
---
features:
  - |
    Adds a persisted audit-to-audit-template relationship for audits created
    with ``audit_template_uuid`` and exposes ``audit_template_uuid`` as an
    optional server-side filter for ``GET /v1/audits`` and
    ``GET /v1/audits/detail``.
upgrade:
  - |
    Adds nullable column ``audits.audit_template_id``. Existing audits are not
    backfilled because previous releases did not persist the source audit
    template on the audit row.
```

- [ ] **Step 7: Sync docs into test mirror for doc builds**

Run:

```bash
rsync -a --exclude=__pycache__ api-ref/source/parameters.yaml /private/tmp/watcher-src-no-colon/api-ref/source/parameters.yaml
rsync -a --exclude=__pycache__ api-ref/source/watcher-api-v1-audits.inc /private/tmp/watcher-src-no-colon/api-ref/source/watcher-api-v1-audits.inc
rsync -a --exclude=__pycache__ releasenotes/notes/audit-template-filter-4f65d2cb0dfd13f2.yaml /private/tmp/watcher-src-no-colon/releasenotes/notes/audit-template-filter-4f65d2cb0dfd13f2.yaml
```

- [ ] **Step 8: Build api-ref**

Run:

```bash
/private/tmp/watcher-venv-py312/bin/sphinx-build -W --keep-going -b html -d api-ref/build/doctrees api-ref/source api-ref/build/html
```

Expected: exit 0.

- [ ] **Step 9: Build release notes**

Run:

```bash
/private/tmp/watcher-venv-py312/bin/sphinx-build -W --keep-going -b html -j auto releasenotes/source releasenotes/build/html
```

Expected: exit 0.

- [ ] **Step 10: Commit docs**

Run:

```bash
git add api-ref/source/parameters.yaml api-ref/source/watcher-api-v1-audits.inc docs/WATCHER_EPOXY_2025_1_ANALYSIS.md docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md releasenotes/notes/audit-template-filter-4f65d2cb0dfd13f2.yaml
git commit -m "Document audit template audit filter"
```

---

### Task 6: Final Verification And Push

**Files:**
- Verify all files changed by Tasks 1-5.

- [ ] **Step 1: Sync all changed code and tests into test mirror**

Run:

```bash
rsync -a --exclude=__pycache__ watcher/tests/db/utils.py /private/tmp/watcher-src-no-colon/watcher/tests/db/utils.py
rsync -a --exclude=__pycache__ watcher/tests/db/test_audit.py /private/tmp/watcher-src-no-colon/watcher/tests/db/test_audit.py
rsync -a --exclude=__pycache__ watcher/tests/api/v1/test_audits.py /private/tmp/watcher-src-no-colon/watcher/tests/api/v1/test_audits.py
rsync -a --exclude=__pycache__ watcher/db/sqlalchemy/models.py /private/tmp/watcher-src-no-colon/watcher/db/sqlalchemy/models.py
rsync -a --exclude=__pycache__ watcher/db/sqlalchemy/api.py /private/tmp/watcher-src-no-colon/watcher/db/sqlalchemy/api.py
rsync -a --exclude=__pycache__ watcher/objects/audit.py /private/tmp/watcher-src-no-colon/watcher/objects/audit.py
rsync -a --exclude=__pycache__ watcher/api/controllers/v1/audit.py /private/tmp/watcher-src-no-colon/watcher/api/controllers/v1/audit.py
```

- [ ] **Step 2: Run focused full audit suites**

Run:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.db.test_audit watcher.tests.api.v1.test_audits
```

Expected: all tests pass.

- [ ] **Step 3: Compile changed Python files**

Run:

```bash
/private/tmp/watcher-venv-py312/bin/python -m py_compile watcher/api/controllers/v1/audit.py watcher/objects/audit.py watcher/db/sqlalchemy/models.py watcher/db/sqlalchemy/api.py watcher/tests/api/v1/test_audits.py watcher/tests/db/test_audit.py watcher/tests/db/utils.py watcher/db/sqlalchemy/alembic/versions/c2f4b8d6e3a1_add_audit_template_id_to_audits.py
```

Expected: exit 0.

- [ ] **Step 4: Check whitespace**

Run:

```bash
git diff --check
```

Expected: no output and exit 0.

- [ ] **Step 5: Inspect final diff**

Run:

```bash
git diff --stat origin/stable/2025.1..HEAD
git status --short --branch
```

Expected: branch is clean except local untracked `.serena/`.

- [ ] **Step 6: Push branch**

Run:

```bash
git push github feature/audit-state-filter-2025.1
```

Expected: push succeeds to
`https://github.com/lebtmalorny-rgb/Watcher.git`.

---

## Self-Review Checklist

- [ ] DB schema stores `audits.audit_template_id`.
- [ ] Audit object exposes internal nullable `audit_template_id`.
- [ ] Audit create with `audit_template_uuid` persists the relationship.
- [ ] Audit list accepts and applies `audit_template_uuid`.
- [ ] Audit detail accepts and applies `audit_template_uuid`.
- [ ] Pagination next links preserve `audit_template_uuid`.
- [ ] Audit response bodies do not expose `audit_template_uuid`.
- [ ] Historical audits remain listable and are not backfilled.
- [ ] Docs state the schema change and Horizon integration behavior.
- [ ] API tests and DB tests pass in the colon-free test mirror.
