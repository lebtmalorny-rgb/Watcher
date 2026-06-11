# Data Model JSON Detail API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add API microversion `1.8` with `detail_format=json` for `GET /v1/data_model`, returning a stable JSON detailed compute data model while preserving `1.7` XML detail and compact responses.

**Architecture:** Add an explicit compute JSON serializer on `ModelRoot`, then thread `detail_format` through REST API, RPC client, and Decision Engine endpoint. Keep XML as the default detailed serializer and require `detail=true&detail_format=json` for JSON output.

**Tech Stack:** Python, Watcher REST controllers with WSME/Pecan, oslo.messaging RPC client, Watcher Decision Engine model classes, stestr, Sphinx api-ref, reno release notes.

---

## Context And Paths

Work from:

```text
/Users/dmitry/Desktop/DRS:HA_fork/watcher
```

Run tests from the colon-free mirror:

```text
/private/tmp/watcher-src-no-colon
```

Use this virtualenv:

```text
/private/tmp/watcher-venv-py312
```

Before running tests, sync changed source files to the mirror. Example:

```bash
rsync -a watcher/tests/decision_engine/model/test_model.py /private/tmp/watcher-src-no-colon/watcher/tests/decision_engine/model/test_model.py
rsync -a watcher/decision_engine/model/model_root.py /private/tmp/watcher-src-no-colon/watcher/decision_engine/model/model_root.py
```

Use this test prefix:

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run <test-module>
```

Do not stage `.serena/`.

## File Structure

Modify:

- `watcher/decision_engine/model/model_root.py`
  - Add the stable JSON detail serializer for compute `ModelRoot`.
  - Keep `to_list()` and `to_string()` unchanged.

- `watcher/tests/decision_engine/model/test_model.py`
  - Add serializer tests that build a real compute model and assert stable JSON shape.

- `watcher/decision_engine/messaging/data_model_endpoint.py`
  - Accept `detail_format=None`.
  - Select `to_list()`, `to_string()`, or `to_dict()` based on `detail` and `detail_format`.

- `watcher/decision_engine/rpcapi.py`
  - Forward `detail_format` to the conductor RPC call.

- `watcher/tests/decision_engine/messaging/test_data_model_endpoint.py`
  - Cover compact, XML detail, JSON detail, and missing model behavior.

- `watcher/tests/decision_engine/test_rpcapi.py`
  - Cover default and explicit `detail_format` forwarding.

- `watcher/api/controllers/v1/versions.py`
  - Add microversion `1.8`.

- `watcher/api/controllers/v1/utils.py`
  - Add `allow_data_model_detail_format()`.

- `watcher/api/controllers/v1/data_model.py`
  - Accept and validate `detail_format`.
  - Preserve all existing behavior when `detail_format` is omitted.

- `watcher/tests/api/v1/test_data_model.py`
  - Cover REST validation and RPC argument forwarding.

- `watcher/tests/api/v1/test_microversions.py`
  - Update latest P2 microversion assertion to `1.8`.

- `watcher/api/controllers/rest_api_version_history.rst`
  - Document API `1.8`.

- `api-ref/source/parameters.yaml`
  - Document `detail_format` query parameter and JSON context shape.

- `api-ref/source/watcher-api-v1-datamodel.inc`
  - Document XML versus JSON detail behavior.

- `api-ref/source/samples/datamodel-list-json-detail-response.json`
  - Add API sample for JSON detail response.

- `docs/specs/CODEX_WATCHER_P2_API_EXTENSIONS.md`
  - Update P2/P2.4 notes with `1.8`.

- `docs/specs/CODEX_WATCHER_HORIZON_BACKEND_IMPLEMENTATION.md`
  - Update Horizon backend contract.

- `docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md`
  - Update integration contract and capability flags.

- `docs/specs/README_WATCHER_HORIZON_GOAL.md`
  - Add `1.8` JSON detail summary.

- `releasenotes/notes/data-model-json-detail-api-8c1d2e3f4a5b6c7d.yaml`
  - Add release note for API `1.8`.

## Task 1: Add Compute JSON Serializer

**Files:**

- Modify: `watcher/tests/decision_engine/model/test_model.py`
- Modify: `watcher/decision_engine/model/model_root.py`

- [ ] **Step 1: Write failing model serializer tests**

Add these helpers and tests to `watcher/tests/decision_engine/model/test_model.py` inside `class TestModel(base.TestCase):`.

```python
    def _make_compute_node(self, uuid, hostname):
        return element.ComputeNode(
            uuid=uuid,
            hostname=hostname,
            status='enabled',
            disabled_reason=None,
            state='up',
            memory=65536,
            memory_mb_reserved=1024,
            disk=1000,
            disk_gb_reserved=10,
            vcpus=32,
            vcpu_reserved=2,
            memory_ratio=1.5,
            vcpu_ratio=16.0,
            disk_ratio=1.0)

    def _make_instance(self, uuid, name, project_id):
        return element.Instance(
            uuid=uuid,
            watcher_exclude=False,
            name=name,
            state='active',
            memory=4096,
            disk=40,
            vcpus=2,
            metadata={'role': 'api'},
            project_id=project_id,
            locked=False)

    def test_model_to_dict_returns_compute_detail_payload(self):
        model = model_root.ModelRoot()
        node = self._make_compute_node('node-1', 'host1')
        instance = self._make_instance(
            'instance-1', 'vm1',
            '11111111-1111-4111-8111-111111111111')
        unmapped = self._make_instance(
            'instance-2', 'vm2',
            '22222222-2222-4222-8222-222222222222')

        model.add_node(node)
        model.add_instance(instance)
        model.add_instance(unmapped)
        model.map_instance(instance, node)

        result = model.to_dict()

        expected = {
            'schema': 'watcher.data_model.detail',
            'schema_version': '1.0',
            'model_type': 'compute',
            'stale': False,
            'data': {
                'compute_nodes': [{
                    'uuid': 'node-1',
                    'hostname': 'host1',
                    'state': 'up',
                    'status': 'enabled',
                    'disabled_reason': None,
                    'resources': {
                        'memory': 65536,
                        'memory_mb_reserved': 1024,
                        'memory_ratio': 1.5,
                        'disk': 1000,
                        'disk_gb_reserved': 10,
                        'disk_ratio': 1.0,
                        'vcpus': 32,
                        'vcpu_reserved': 2,
                        'vcpu_ratio': 16.0,
                    },
                    'instances': [{
                        'uuid': 'instance-1',
                        'name': 'vm1',
                        'state': 'active',
                        'vcpus': 2,
                        'memory': 4096,
                        'disk': 40,
                        'watcher_exclude': False,
                        'project_id': '11111111-1111-4111-8111-111111111111',
                        'locked': False,
                        'metadata': {'role': 'api'},
                    }],
                }],
                'unmapped_instances': [{
                    'uuid': 'instance-2',
                    'name': 'vm2',
                    'state': 'active',
                    'vcpus': 2,
                    'memory': 4096,
                    'disk': 40,
                    'watcher_exclude': False,
                    'project_id': '22222222-2222-4222-8222-222222222222',
                    'locked': False,
                    'metadata': {'role': 'api'},
                }],
            },
        }
        self.assertEqual(expected, result)

    def test_model_to_dict_sorts_nodes_instances_and_unmapped_instances(self):
        model = model_root.ModelRoot()
        node_b = self._make_compute_node('node-b', 'host-b')
        node_a = self._make_compute_node('node-a', 'host-a')
        instance_b = self._make_instance(
            'instance-b', 'vm-b',
            '33333333-3333-4333-8333-333333333333')
        instance_a = self._make_instance(
            'instance-a', 'vm-a',
            '44444444-4444-4444-8444-444444444444')
        unmapped_b = self._make_instance(
            'unmapped-b', 'vm-unmapped-b',
            '55555555-5555-4555-8555-555555555555')
        unmapped_a = self._make_instance(
            'unmapped-a', 'vm-unmapped-a',
            '66666666-6666-4666-8666-666666666666')

        model.add_node(node_b)
        model.add_node(node_a)
        model.add_instance(instance_b)
        model.add_instance(instance_a)
        model.add_instance(unmapped_b)
        model.add_instance(unmapped_a)
        model.map_instance(instance_b, node_b)
        model.map_instance(instance_a, node_b)

        data = model.to_dict()['data']

        self.assertEqual(
            ['node-a', 'node-b'],
            [node['uuid'] for node in data['compute_nodes']])
        self.assertEqual(
            ['instance-a', 'instance-b'],
            [inst['uuid'] for inst in data['compute_nodes'][1]['instances']])
        self.assertEqual(
            ['unmapped-a', 'unmapped-b'],
            [inst['uuid'] for inst in data['unmapped_instances']])
```

- [ ] **Step 2: Run the RED model tests**

Sync and run:

```bash
rsync -a watcher/tests/decision_engine/model/test_model.py /private/tmp/watcher-src-no-colon/watcher/tests/decision_engine/model/test_model.py
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.decision_engine.model.test_model
```

Expected: FAIL with `AttributeError: 'ModelRoot' object has no attribute 'to_dict'`.

- [ ] **Step 3: Implement the compute JSON serializer**

In `watcher/decision_engine/model/model_root.py`, add these constants below `LOG = log.getLogger(__name__)`:

```python
DETAIL_SCHEMA = 'watcher.data_model.detail'
DETAIL_SCHEMA_VERSION = '1.0'

_COMPUTE_NODE_FIELDS = (
    'uuid', 'hostname', 'state', 'status', 'disabled_reason')
_COMPUTE_RESOURCE_FIELDS = (
    'memory', 'memory_mb_reserved', 'memory_ratio',
    'disk', 'disk_gb_reserved', 'disk_ratio',
    'vcpus', 'vcpu_reserved', 'vcpu_ratio')
_INSTANCE_FIELDS = (
    'uuid', 'name', 'state', 'vcpus', 'memory', 'disk',
    'watcher_exclude', 'project_id', 'locked', 'metadata')
```

Add this helper below the constants:

```python
def _field_value(obj, field, default=None):
    try:
        return obj[field]
    except Exception:
        return default
```

Add these methods to `class ModelRoot`, immediately before existing `to_string()`:

```python
    def _instance_to_dict(self, instance):
        return {
            field: _field_value(instance, field)
            for field in _INSTANCE_FIELDS
        }

    def _compute_node_to_dict(self, node):
        node_data = {
            field: _field_value(node, field)
            for field in _COMPUTE_NODE_FIELDS
        }
        node_data['resources'] = {
            field: _field_value(node, field)
            for field in _COMPUTE_RESOURCE_FIELDS
        }
        node_data['instances'] = [
            self._instance_to_dict(instance)
            for instance in sorted(
                self.get_node_instances(node),
                key=lambda instance: instance.uuid)
        ]
        return node_data

    def to_dict(self):
        compute_nodes = [
            self._compute_node_to_dict(node)
            for node in sorted(
                self.get_all_compute_nodes().values(),
                key=lambda node: node.uuid)
        ]

        unmapped_instances = []
        for instance in sorted(
                self.get_all_instances().values(),
                key=lambda instance: instance.uuid):
            try:
                self.get_node_by_instance_uuid(instance.uuid)
            except exception.InstanceNotMapped:
                unmapped_instances.append(self._instance_to_dict(instance))

        return {
            'schema': DETAIL_SCHEMA,
            'schema_version': DETAIL_SCHEMA_VERSION,
            'model_type': 'compute',
            'stale': self.stale,
            'data': {
                'compute_nodes': compute_nodes,
                'unmapped_instances': unmapped_instances,
            },
        }
```

- [ ] **Step 4: Run the GREEN model tests**

Sync and run:

```bash
rsync -a watcher/decision_engine/model/model_root.py /private/tmp/watcher-src-no-colon/watcher/decision_engine/model/model_root.py
rsync -a watcher/tests/decision_engine/model/test_model.py /private/tmp/watcher-src-no-colon/watcher/tests/decision_engine/model/test_model.py
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.decision_engine.model.test_model
```

Expected: PASS.

- [ ] **Step 5: Commit the model serializer**

```bash
git add watcher/decision_engine/model/model_root.py watcher/tests/decision_engine/model/test_model.py
git commit -m "Add compute data model JSON serializer"
```

## Task 2: Thread `detail_format` Through Endpoint And RPC

**Files:**

- Modify: `watcher/tests/decision_engine/messaging/test_data_model_endpoint.py`
- Modify: `watcher/tests/decision_engine/test_rpcapi.py`
- Modify: `watcher/decision_engine/messaging/data_model_endpoint.py`
- Modify: `watcher/decision_engine/rpcapi.py`

- [ ] **Step 1: Write failing endpoint tests**

In `watcher/tests/decision_engine/messaging/test_data_model_endpoint.py`, update the existing detail serializer test to assert XML default:

```python
    def test_get_data_model_info_uses_xml_detail_serializer(self):
        available_model = mock.Mock()
        available_model.to_string.return_value = '<ModelRoot />'
        self._patch_collector_model(available_model)

        result = self.endpoint_instance.get_data_model_info(
            context='fake', detail=True)

        self.assertEqual({'context': '<ModelRoot />'}, result)
        available_model.to_string.assert_called_once_with()
        available_model.to_list.assert_not_called()
        available_model.to_dict.assert_not_called()
```

Rename any existing `test_get_data_model_info_uses_detail_serializer` to this name.

Add JSON detail and XML explicit tests:

```python
    def test_get_data_model_info_uses_json_detail_serializer(self):
        available_model = mock.Mock()
        available_model.to_dict.return_value = {
            'schema': 'watcher.data_model.detail',
            'schema_version': '1.0',
            'model_type': 'compute',
            'stale': False,
            'data': {'compute_nodes': [], 'unmapped_instances': []},
        }
        self._patch_collector_model(available_model)

        result = self.endpoint_instance.get_data_model_info(
            context='fake', detail=True, detail_format='json')

        self.assertEqual({
            'context': {
                'schema': 'watcher.data_model.detail',
                'schema_version': '1.0',
                'model_type': 'compute',
                'stale': False,
                'data': {'compute_nodes': [], 'unmapped_instances': []},
            }}, result)
        available_model.to_dict.assert_called_once_with()
        available_model.to_string.assert_not_called()
        available_model.to_list.assert_not_called()

    def test_get_data_model_info_uses_xml_serializer_when_requested(self):
        available_model = mock.Mock()
        available_model.to_string.return_value = '<ModelRoot />'
        self._patch_collector_model(available_model)

        result = self.endpoint_instance.get_data_model_info(
            context='fake', detail=True, detail_format='xml')

        self.assertEqual({'context': '<ModelRoot />'}, result)
        available_model.to_string.assert_called_once_with()
        available_model.to_dict.assert_not_called()
        available_model.to_list.assert_not_called()

    def test_get_data_model_info_returns_empty_context_for_json_without_model(
            self):
        self._patch_collector_model(None)

        result = self.endpoint_instance.get_data_model_info(
            context='fake', detail=True, detail_format='json')

        self.assertEqual({'context': []}, result)
```

- [ ] **Step 2: Update failing RPC tests**

In `watcher/tests/decision_engine/test_rpcapi.py`, update the default expected call in `test_get_data_model_info`:

```python
            mock_call.assert_called_once_with(
                self.context, 'get_data_model_info',
                data_model_type='compute',
                audit=None,
                detail=False,
                detail_format=None)
```

Update `test_get_data_model_info_with_detail` expected call:

```python
            mock_call.assert_called_once_with(
                self.context, 'get_data_model_info',
                data_model_type='compute',
                audit=None,
                detail=True,
                detail_format=None)
```

Add this test:

```python
    def test_get_data_model_info_with_detail_format(self):
        with mock.patch.object(om.RPCClient, 'call') as mock_call:
            self.api.get_data_model_info(
                self.context,
                data_model_type='compute',
                audit=None,
                detail=True,
                detail_format='json')
            mock_call.assert_called_once_with(
                self.context, 'get_data_model_info',
                data_model_type='compute',
                audit=None,
                detail=True,
                detail_format='json')
```

- [ ] **Step 3: Run RED endpoint and RPC tests**

Sync and run:

```bash
rsync -a watcher/tests/decision_engine/messaging/test_data_model_endpoint.py /private/tmp/watcher-src-no-colon/watcher/tests/decision_engine/messaging/test_data_model_endpoint.py
rsync -a watcher/tests/decision_engine/test_rpcapi.py /private/tmp/watcher-src-no-colon/watcher/tests/decision_engine/test_rpcapi.py
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.decision_engine.messaging.test_data_model_endpoint watcher.tests.decision_engine.test_rpcapi
```

Expected: FAIL because `detail_format` is not accepted or forwarded.

- [ ] **Step 4: Implement endpoint and RPC plumbing**

In `watcher/decision_engine/rpcapi.py`, change the method signature and call:

```python
    def get_data_model_info(self, context, data_model_type, audit,
                            detail=False, detail_format=None):
        return self.conductor_client.call(
            context, 'get_data_model_info',
            data_model_type=data_model_type, audit=audit, detail=detail,
            detail_format=detail_format)
```

In `watcher/decision_engine/messaging/data_model_endpoint.py`, change the method signature and serializer branch:

```python
    def get_data_model_info(self, context, data_model_type='compute',
                            audit=None, detail=False, detail_format=None):
```

Replace the serializer tail with:

```python
        if not available_data_model:
            return {"context": []}
        if detail:
            if detail_format == 'json':
                return {"context": available_data_model.to_dict()}
            return {"context": available_data_model.to_string()}
        return {"context": available_data_model.to_list()}
```

- [ ] **Step 5: Run GREEN endpoint and RPC tests**

Sync and run:

```bash
rsync -a watcher/decision_engine/rpcapi.py /private/tmp/watcher-src-no-colon/watcher/decision_engine/rpcapi.py
rsync -a watcher/decision_engine/messaging/data_model_endpoint.py /private/tmp/watcher-src-no-colon/watcher/decision_engine/messaging/data_model_endpoint.py
rsync -a watcher/tests/decision_engine/messaging/test_data_model_endpoint.py /private/tmp/watcher-src-no-colon/watcher/tests/decision_engine/messaging/test_data_model_endpoint.py
rsync -a watcher/tests/decision_engine/test_rpcapi.py /private/tmp/watcher-src-no-colon/watcher/tests/decision_engine/test_rpcapi.py
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.decision_engine.messaging.test_data_model_endpoint watcher.tests.decision_engine.test_rpcapi
```

Expected: PASS.

- [ ] **Step 6: Commit endpoint and RPC plumbing**

```bash
git add watcher/decision_engine/rpcapi.py watcher/decision_engine/messaging/data_model_endpoint.py watcher/tests/decision_engine/messaging/test_data_model_endpoint.py watcher/tests/decision_engine/test_rpcapi.py
git commit -m "Thread data model detail format through RPC"
```

## Task 3: Add REST API Microversion 1.8 And Validation

**Files:**

- Modify: `watcher/tests/api/v1/test_data_model.py`
- Modify: `watcher/tests/api/v1/test_microversions.py`
- Modify: `watcher/api/controllers/v1/versions.py`
- Modify: `watcher/api/controllers/v1/utils.py`
- Modify: `watcher/api/controllers/v1/data_model.py`

- [ ] **Step 1: Write failing API tests**

In `watcher/tests/api/v1/test_data_model.py`, update existing assertions so all RPC calls include `detail_format=None`.

Example for compact calls:

```python
        self.mock_dcapi_client.get_data_model_info.assert_called_once_with(
            mock.ANY, 'compute', None, detail=False, detail_format=None)
```

Example for existing XML detail calls:

```python
        self.mock_dcapi_client.get_data_model_info.assert_called_once_with(
            mock.ANY, 'compute', None, detail=True, detail_format=None)
```

Add these tests to `class TestListDataModel(api_base.FunctionalTest):`

```python
    def test_get_all_with_detail_format_json(self):
        response = self.get_json(
            '/data_model/?data_model_type=compute&detail=true'
            '&detail_format=json',
            headers={'OpenStack-API-Version': 'infra-optim 1.8'})
        self.assertEqual('fake_response_value', response)
        self.mock_dcapi_client.get_data_model_info.assert_called_once_with(
            mock.ANY, 'compute', None, detail=True, detail_format='json')

    def test_get_all_with_detail_format_xml(self):
        response = self.get_json(
            '/data_model/?data_model_type=compute&detail=true'
            '&detail_format=xml',
            headers={'OpenStack-API-Version': 'infra-optim 1.8'})
        self.assertEqual('fake_response_value', response)
        self.mock_dcapi_client.get_data_model_info.assert_called_once_with(
            mock.ANY, 'compute', None, detail=True, detail_format='xml')

    def test_get_all_detail_true_1_8_without_format_keeps_default(self):
        response = self.get_json(
            '/data_model/?data_model_type=compute&detail=true',
            headers={'OpenStack-API-Version': 'infra-optim 1.8'})
        self.assertEqual('fake_response_value', response)
        self.mock_dcapi_client.get_data_model_info.assert_called_once_with(
            mock.ANY, 'compute', None, detail=True, detail_format=None)

    def test_get_all_detail_format_not_acceptable_before_1_8(self):
        response = self.get_json(
            '/data_model/?data_model_type=compute&detail=true'
            '&detail_format=json',
            headers={'OpenStack-API-Version': 'infra-optim 1.7'},
            expect_errors=True)
        self.assertEqual(HTTPStatus.NOT_ACCEPTABLE, response.status_int)
        self.mock_dcapi_client.get_data_model_info.assert_not_called()

    def test_get_all_invalid_detail_format(self):
        response = self.get_json(
            '/data_model/?data_model_type=compute&detail=true'
            '&detail_format=yaml',
            headers={'OpenStack-API-Version': 'infra-optim 1.8'},
            expect_errors=True)
        self.assertEqual(HTTPStatus.BAD_REQUEST, response.status_int)
        self.mock_dcapi_client.get_data_model_info.assert_not_called()

    def test_get_all_detail_format_requires_detail_true(self):
        response = self.get_json(
            '/data_model/?data_model_type=compute&detail_format=json',
            headers={'OpenStack-API-Version': 'infra-optim 1.8'},
            expect_errors=True)
        self.assertEqual(HTTPStatus.BAD_REQUEST, response.status_int)
        self.mock_dcapi_client.get_data_model_info.assert_not_called()

    def test_get_all_detail_format_rejects_detail_false(self):
        response = self.get_json(
            '/data_model/?data_model_type=compute&detail=false'
            '&detail_format=json',
            headers={'OpenStack-API-Version': 'infra-optim 1.8'},
            expect_errors=True)
        self.assertEqual(HTTPStatus.BAD_REQUEST, response.status_int)
        self.mock_dcapi_client.get_data_model_info.assert_not_called()

    def test_get_all_detail_format_does_not_enable_storage_type(self):
        response = self.get_json(
            '/data_model/?data_model_type=storage&detail=true'
            '&detail_format=json',
            headers={'OpenStack-API-Version': 'infra-optim 1.8'},
            expect_errors=True)
        self.assertEqual(HTTPStatus.NOT_FOUND, response.status_int)
        self.mock_dcapi_client.get_data_model_info.assert_not_called()
```

In `watcher/tests/api/v1/test_microversions.py`, update:

```python
    def test_p2_data_model_json_detail_is_latest_microversion(self):
        self.assertEqual('1.8', versions.max_version_string())
```

- [ ] **Step 2: Run RED API tests**

Sync and run:

```bash
rsync -a watcher/tests/api/v1/test_data_model.py /private/tmp/watcher-src-no-colon/watcher/tests/api/v1/test_data_model.py
rsync -a watcher/tests/api/v1/test_microversions.py /private/tmp/watcher-src-no-colon/watcher/tests/api/v1/test_microversions.py
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.api.v1.test_data_model watcher.tests.api.v1.test_microversions
```

Expected: FAIL because API `1.8` is unsupported and `detail_format` is not accepted.

- [ ] **Step 3: Add microversion 1.8**

In `watcher/api/controllers/v1/versions.py`, update enum values:

```python
    MINOR_7_DATA_MODEL_DETAIL = 7  # v1.7: Add data model detail API
    MINOR_8_DATA_MODEL_JSON_DETAIL = 8  # v1.8: Add data model JSON detail
    MINOR_MAX_VERSION = 8
```

In `watcher/api/controllers/v1/utils.py`, add:

```python
def allow_data_model_detail_format():
    """Check if we should support the data model detail_format parameter.

    Version 1.8 of the API added support for JSON detailed data model output.
    """
    return pecan.request.version.minor >= (
        versions.VERSIONS.MINOR_8_DATA_MODEL_JSON_DETAIL.value)
```

- [ ] **Step 4: Implement REST parsing and validation**

In `watcher/api/controllers/v1/data_model.py`, add constants near existing `_TRUE_VALUES`:

```python
_DETAIL_FORMAT_JSON = 'json'
_DETAIL_FORMAT_XML = 'xml'
_DETAIL_FORMATS = (_DETAIL_FORMAT_JSON, _DETAIL_FORMAT_XML)
```

Add parser below `_parse_detail()`:

```python
def _parse_detail_format(detail_format):
    if not _is_set(detail_format):
        return None

    value = detail_format.lower()
    if value in _DETAIL_FORMATS:
        return value

    raise exception.Invalid(
        _('Invalid detail_format value: %s. Acceptable values are '
          'json or xml.') % detail_format)
```

Change the `wsexpose` decorator and method signature:

```python
    @wsme_pecan.wsexpose(wtypes.text, wtypes.text, types.uuid, wtypes.text,
                         wtypes.text)
    def get_all(self, data_model_type='compute', audit_uuid=None,
                detail=None, detail_format=None):
```

Inside `get_all()`, replace the detail validation block with:

```python
        detail_requested = _is_set(detail)
        detail_format_requested = _is_set(detail_format)
        if detail_requested and not utils.allow_data_model_detail():
            raise exception.NotAcceptable
        if detail_format_requested and not (
                utils.allow_data_model_detail_format()):
            raise exception.NotAcceptable
        detail = _parse_detail(detail)
        detail_format = _parse_detail_format(detail_format)
        if detail_format and not detail:
            raise exception.Invalid(
                _('detail_format requires detail=true.'))
```

Update the RPC call:

```python
        rpc_all_data_model = de_client.get_data_model_info(
            context,
            data_model_type,
            audit_uuid,
            detail=detail,
            detail_format=detail_format)
```

- [ ] **Step 5: Run GREEN API tests**

Sync and run:

```bash
rsync -a watcher/api/controllers/v1/versions.py /private/tmp/watcher-src-no-colon/watcher/api/controllers/v1/versions.py
rsync -a watcher/api/controllers/v1/utils.py /private/tmp/watcher-src-no-colon/watcher/api/controllers/v1/utils.py
rsync -a watcher/api/controllers/v1/data_model.py /private/tmp/watcher-src-no-colon/watcher/api/controllers/v1/data_model.py
rsync -a watcher/tests/api/v1/test_data_model.py /private/tmp/watcher-src-no-colon/watcher/tests/api/v1/test_data_model.py
rsync -a watcher/tests/api/v1/test_microversions.py /private/tmp/watcher-src-no-colon/watcher/tests/api/v1/test_microversions.py
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.api.v1.test_data_model watcher.tests.api.v1.test_microversions
```

Expected: PASS.

- [ ] **Step 6: Run root version smoke tests**

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.api.test_root
```

Expected: PASS.

- [ ] **Step 7: Commit REST API support**

```bash
git add watcher/api/controllers/v1/versions.py watcher/api/controllers/v1/utils.py watcher/api/controllers/v1/data_model.py watcher/tests/api/v1/test_data_model.py watcher/tests/api/v1/test_microversions.py
git commit -m "Add data model JSON detail API"
```

## Task 4: Update API Documentation And Release Notes

**Files:**

- Modify: `watcher/api/controllers/rest_api_version_history.rst`
- Modify: `api-ref/source/parameters.yaml`
- Modify: `api-ref/source/watcher-api-v1-datamodel.inc`
- Create: `api-ref/source/samples/datamodel-list-json-detail-response.json`
- Create: `releasenotes/notes/data-model-json-detail-api-8c1d2e3f4a5b6c7d.yaml`
- Modify: `docs/specs/CODEX_WATCHER_P2_API_EXTENSIONS.md`
- Modify: `docs/specs/CODEX_WATCHER_HORIZON_BACKEND_IMPLEMENTATION.md`
- Modify: `docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md`
- Modify: `docs/specs/README_WATCHER_HORIZON_GOAL.md`

- [ ] **Step 1: Update REST API version history**

Append to `watcher/api/controllers/rest_api_version_history.rst`:

```rst
1.8
---
Added the optional ``detail_format`` query parameter to the Data Model API::

  GET /v1/data_model?detail=true&detail_format=json

When ``detail_format=json`` is requested with ``detail=true``, ``context``
contains the stable JSON data model detail object. Omitting ``detail_format``
keeps the existing XML detail behavior.
```

- [ ] **Step 2: Update api-ref parameters**

In `api-ref/source/parameters.yaml`, add query parameter `r_data_model_detail_format` in sorted query order after `r_data_model_detail`:

```yaml
r_data_model_detail_format:
  description: |
    Optional detailed data model response format. Valid values are ``xml`` and
    ``json``. This parameter requires ``detail=true``. When omitted with
    ``detail=true``, the response keeps the XML detail format. The ``json``
    format returns a stable JSON object in ``context``.
  in: query
  required: false
  type: string
  min_version: 1.8
```

Update `data_model_context` description:

```yaml
data_model_context:
  description: |
    Data model payload. For the compact response this is a list of flattened
    compute node and server mappings. Starting with API microversion 1.7,
    when ``detail=true`` is requested without ``detail_format=json``, this
    field is an XML string produced by the data model serializer. Starting
    with API microversion 1.8, when ``detail=true&detail_format=json`` is
    requested, this field is a stable JSON detail object.
  in: body
  required: true
  type: array, string, or object
```

- [ ] **Step 3: Update data model api-ref page**

In `api-ref/source/watcher-api-v1-datamodel.inc`, add `detail_format` under request parameters:

```rst
   - detail_format: r_data_model_detail_format
```

Add a `versionchanged` note:

```rst
.. versionchanged:: 1.8

   Added ``detail_format=json`` for ``detail=true`` requests. The default
   detailed format remains XML.
```

Add a JSON detail sample include:

```rst
**Example JSON representation of a JSON detailed Data Model:**

.. literalinclude:: samples/datamodel-list-json-detail-response.json
   :language: javascript
```

- [ ] **Step 4: Add JSON detail sample**

Create `api-ref/source/samples/datamodel-list-json-detail-response.json`:

```json
{
    "context": {
        "schema": "watcher.data_model.detail",
        "schema_version": "1.0",
        "model_type": "compute",
        "stale": false,
        "data": {
            "compute_nodes": [
                {
                    "uuid": "253e5dd0-9384-41ab-af13-4f2c2ce26112",
                    "hostname": "localhost.localdomain",
                    "state": "up",
                    "status": "enabled",
                    "disabled_reason": null,
                    "resources": {
                        "memory": 16383,
                        "memory_mb_reserved": 0,
                        "memory_ratio": 1.5,
                        "disk": 37,
                        "disk_gb_reserved": 0,
                        "disk_ratio": 1.0,
                        "vcpus": 4,
                        "vcpu_reserved": 0,
                        "vcpu_ratio": 16.0
                    },
                    "instances": [
                        {
                            "uuid": "1bf91464-9b41-428d-a11e-af691e5563bb",
                            "name": "chenke-test1",
                            "state": "active",
                            "vcpus": 1,
                            "memory": 512,
                            "disk": 1,
                            "watcher_exclude": false,
                            "project_id": "11111111-1111-4111-8111-111111111111",
                            "locked": false,
                            "metadata": {}
                        }
                    ]
                }
            ],
            "unmapped_instances": []
        }
    }
}
```

- [ ] **Step 5: Add release note**

Create `releasenotes/notes/data-model-json-detail-api-8c1d2e3f4a5b6c7d.yaml`:

```yaml
---
features:
  - |
    Adds REST API microversion 1.8 with ``detail_format=json`` for
    ``GET /v1/data_model`` detailed responses. The new format requires
    ``detail=true`` and returns a stable JSON object in ``context``. Existing
    compact responses and the API 1.7 XML detail behavior are unchanged.
```

- [ ] **Step 6: Update Russian/contract docs**

Update these docs so they state:

```text
1.8 - detail_format=json для GET /v1/data_model
```

and include these compatibility rules:

```text
API 1.7 detail=true keeps XML context.
API 1.8 detail=true without detail_format keeps XML context.
API 1.8 detail=true&detail_format=json returns JSON object context.
Horizon should request detail_format=json only after negotiating API >= 1.8.
```

Files:

```text
docs/specs/CODEX_WATCHER_P2_API_EXTENSIONS.md
docs/specs/CODEX_WATCHER_HORIZON_BACKEND_IMPLEMENTATION.md
docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md
docs/specs/README_WATCHER_HORIZON_GOAL.md
```

- [ ] **Step 7: Build docs**

Sync docs and run:

```bash
rsync -a api-ref docs releasenotes watcher /private/tmp/watcher-src-no-colon/
/private/tmp/watcher-venv-py312/bin/sphinx-build -W --keep-going -b html -d api-ref/build/doctrees api-ref/source api-ref/build/html
/private/tmp/watcher-venv-py312/bin/sphinx-build -W --keep-going -b html -j auto releasenotes/source releasenotes/build/html
```

Expected: both builds succeed.

- [ ] **Step 8: Commit docs**

```bash
git add watcher/api/controllers/rest_api_version_history.rst api-ref/source/parameters.yaml api-ref/source/watcher-api-v1-datamodel.inc api-ref/source/samples/datamodel-list-json-detail-response.json releasenotes/notes/data-model-json-detail-api-8c1d2e3f4a5b6c7d.yaml docs/specs/CODEX_WATCHER_P2_API_EXTENSIONS.md docs/specs/CODEX_WATCHER_HORIZON_BACKEND_IMPLEMENTATION.md docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md docs/specs/README_WATCHER_HORIZON_GOAL.md
git commit -m "Document data model JSON detail API"
```

## Task 5: Final Verification And Push

**Files:**

- Verify all changed files.
- No code edits in this task unless verification identifies a concrete failure.

- [ ] **Step 1: Sync repository to mirror**

```bash
rsync -a --exclude=__pycache__ api-ref docs releasenotes watcher /private/tmp/watcher-src-no-colon/
```

- [ ] **Step 2: Run focused backend test suite**

```bash
OS_STDOUT_CAPTURE=1 OS_STDERR_CAPTURE=1 OS_TEST_TIMEOUT=30 PYTHONDONTWRITEBYTECODE=1 /private/tmp/watcher-venv-py312/bin/stestr run watcher.tests.decision_engine.model.test_model watcher.tests.decision_engine.messaging.test_data_model_endpoint watcher.tests.decision_engine.test_rpcapi watcher.tests.api.v1.test_data_model watcher.tests.api.v1.test_microversions watcher.tests.api.test_root
```

Expected: PASS.

- [ ] **Step 3: Run Python syntax check**

```bash
/private/tmp/watcher-venv-py312/bin/python -m py_compile watcher/decision_engine/model/model_root.py watcher/decision_engine/messaging/data_model_endpoint.py watcher/decision_engine/rpcapi.py watcher/api/controllers/v1/data_model.py watcher/api/controllers/v1/utils.py watcher/api/controllers/v1/versions.py watcher/tests/decision_engine/model/test_model.py watcher/tests/decision_engine/messaging/test_data_model_endpoint.py watcher/tests/decision_engine/test_rpcapi.py watcher/tests/api/v1/test_data_model.py watcher/tests/api/v1/test_microversions.py
```

Expected: no output and exit code `0`.

- [ ] **Step 4: Run docs builds**

```bash
/private/tmp/watcher-venv-py312/bin/sphinx-build -W --keep-going -b html -d api-ref/build/doctrees api-ref/source api-ref/build/html
/private/tmp/watcher-venv-py312/bin/sphinx-build -W --keep-going -b html -j auto releasenotes/source releasenotes/build/html
```

Expected: both builds succeed.

- [ ] **Step 5: Run git checks**

```bash
git diff --check
git status --short --branch
```

Expected: `git diff --check` has no output. Status shows only intended changes or a clean tree plus untracked `.serena/`.

- [ ] **Step 6: Push branch**

```bash
git push github feature/audit-state-filter-2025.1
```

Expected: remote branch updates successfully.

## Self-Review Checklist

- Spec requirement "do not change API 1.7 XML detail" is covered by Task 3 API tests and Task 4 docs.
- Spec requirement "future-safe envelope" is covered by Task 1 serializer tests and implementation.
- Spec requirement "compute implementation first" is covered by Task 1 and Task 2.
- Spec requirement "storage/baremetal reserved but not exposed" is covered by Task 4 docs and absence of REST allowlist changes.
- Spec requirement "detail_format requires detail=true" is covered by Task 3 validation tests.
- Spec requirement "docs and release note" is covered by Task 4.
- Verification commands are listed in Task 5.
