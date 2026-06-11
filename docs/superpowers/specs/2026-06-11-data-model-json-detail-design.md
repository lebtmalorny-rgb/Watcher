# Data Model JSON Detail API Design

## Objective

Add a future-safe JSON detailed representation for the Watcher Data Model API
without changing the API 1.7 XML detail behavior and without changing the
existing compact `GET /v1/data_model` response.

This is a backend API contract design for the Watcher repository. Horizon
plugin implementation and integration tests remain out of scope.

## Current State

The branch already implements API microversion `1.7`:

```http
GET /v1/data_model?detail=true
OpenStack-API-Version: infra-optim 1.7
```

In `1.7`, `detail=true` returns:

```text
context = available_data_model.to_string()
```

For the compute data model, this is an XML string rooted at `<ModelRoot>`.
This must remain stable for API `1.7` clients.

The compact behavior remains:

```http
GET /v1/data_model
GET /v1/data_model?data_model_type=compute
GET /v1/data_model?data_model_type=compute&audit_uuid=<AUDIT_UUID>
```

and returns:

```text
context = available_data_model.to_list()
```

## Proposed API

Add API microversion `1.8` with an explicit JSON detail format:

```http
GET /v1/data_model?data_model_type=compute&detail=true&detail_format=json
OpenStack-API-Version: infra-optim 1.8
```

Compatibility matrix:

```text
1.7 detail=true                         -> context = XML string
1.8 detail=true                         -> context = XML string
1.8 detail=true&detail_format=json      -> context = JSON object
```

The existing XML detail behavior remains available in `1.8` when
`detail_format` is omitted.

## Validation Contract

`detail_format` is accepted only in API microversion `1.8` or newer.

Valid values:

```text
xml
json
```

Rules:

- `detail_format=json` requires `detail=true`.
- `detail_format=xml` requires `detail=true`.
- `detail_format` before API `1.8` returns `406 Not Acceptable`.
- invalid `detail_format` returns `400 Bad Request`.
- `detail_format=json` with `detail=false` or without `detail` returns
  `400 Bad Request`.
- omitting `detail_format` preserves current behavior:
  - `detail=false` or omitted returns compact list;
  - `detail=true` returns XML string.

## JSON Envelope

The JSON representation uses a stable envelope so future model types can be
added without changing the top-level contract:

```json
{
  "context": {
    "schema": "watcher.data_model.detail",
    "schema_version": "1.0",
    "model_type": "compute",
    "stale": false,
    "data": {}
  }
}
```

Fields:

- `schema`: fixed schema identifier.
- `schema_version`: JSON detail schema version, independent from the REST API
  microversion.
- `model_type`: requested data model type.
- `stale`: boolean value from the model root when available.
- `data`: type-specific payload.

## Compute Payload

Initial implementation should support only the currently exposed REST type:
`compute`.

Payload:

```json
{
  "compute_nodes": [
    {
      "uuid": "node-uuid",
      "hostname": "host1",
      "state": "up",
      "status": "enabled",
      "disabled_reason": null,
      "resources": {
        "memory": 65536,
        "memory_mb_reserved": 0,
        "memory_ratio": 1.5,
        "disk": 1000,
        "disk_gb_reserved": 0,
        "disk_ratio": 1.0,
        "vcpus": 32,
        "vcpu_reserved": 0,
        "vcpu_ratio": 16.0
      },
      "instances": [
        {
          "uuid": "instance-uuid",
          "name": "vm1",
          "state": "active",
          "vcpus": 2,
          "memory": 4096,
          "disk": 40,
          "watcher_exclude": false,
          "project_id": "project-uuid",
          "locked": false,
          "metadata": {}
        }
      ]
    }
  ],
  "unmapped_instances": []
}
```

Ordering:

- `compute_nodes` are sorted by `uuid`.
- each node's `instances` are sorted by `uuid`.
- `unmapped_instances` are sorted by `uuid`.

The serializer must use explicit field allowlists. It must not dump NetworkX
graph internals, Watcher object internals, or arbitrary Python object state.

## Future Storage Payload

The API design reserves this shape for a future `data_model_type=storage`
implementation. It should not be exposed until the REST controller supports
`storage`.

```json
{
  "storage_nodes": [
    {
      "uuid": "storage-node-uuid",
      "human_id": "storage-human-id",
      "host": "host@backend",
      "zone": "nova",
      "state": "up",
      "status": "enabled",
      "volume_type": [],
      "pools": [
        {
          "uuid": "pool-uuid",
          "human_id": "pool-human-id",
          "name": "pool-name",
          "total_volumes": 10,
          "total_capacity_gb": 1000,
          "free_capacity_gb": 500,
          "provisioned_capacity_gb": 600,
          "allocated_capacity_gb": 400,
          "virtual_free": 500,
          "volumes": []
        }
      ]
    }
  ],
  "unmapped_volumes": []
}
```

## Future Baremetal Payload

The API design reserves this shape for a future `data_model_type=baremetal`
implementation. It should not be exposed until the REST controller supports
`baremetal`.

```json
{
  "ironic_nodes": [
    {
      "uuid": "ironic-node-uuid",
      "human_id": "node-name",
      "power_state": "power on",
      "maintenance": false,
      "maintenance_reason": null,
      "extra": {}
    }
  ]
}
```

## Implementation Shape

Recommended model-layer API:

```python
available_data_model.to_dict(model_type='compute')
```

Alternative name:

```python
available_data_model.to_json_dict(model_type='compute')
```

The method should return only the JSON object stored in `context`, not the REST
response envelope.

The Decision Engine endpoint should choose the serializer:

```text
detail=false                         -> to_list()
detail=true, no detail_format         -> to_string()
detail=true, detail_format=xml        -> to_string()
detail=true, detail_format=json       -> to_dict()
```

The API controller should parse and validate `detail_format`, then pass it
through:

```text
DataModelController.get_all(..., detail_format=None)
DecisionEngineAPI.get_data_model_info(..., detail=False, detail_format=None)
DataModelEndpoint.get_data_model_info(..., detail=False, detail_format=None)
```

## Compatibility Rules

Do not change:

- API `1.7` XML detail behavior;
- compact `GET /v1/data_model` response;
- compact `to_list()` format;
- allowed `data_model_type` values in the REST controller.

Do not expose:

- internal NetworkX graph structure;
- raw Watcher object internals;
- arbitrary fields not included in the allowlists;
- storage or baremetal REST support before those types are intentionally
  enabled and tested.

## Documentation Updates

Required documentation:

- `watcher/api/controllers/rest_api_version_history.rst`
- `api-ref/source/watcher-api-v1-datamodel.inc`
- `api-ref/source/parameters.yaml`
- `docs/specs/CODEX_WATCHER_P2_API_EXTENSIONS.md`
- `docs/specs/CODEX_WATCHER_HORIZON_BACKEND_IMPLEMENTATION.md`
- `docs/WATCHER_HORIZON_INTEGRATION_API_CHANGES.md`
- release note under `releasenotes/notes/`

Docs must state that `detail_format=json` is API `1.8+` and that API `1.7`
continues to return XML for `detail=true`.

## Test Plan

API tests:

- API max version becomes `1.8`.
- `detail_format=json` before `1.8` returns `406`.
- invalid `detail_format` returns `400`.
- `detail_format=json` without `detail=true` returns `400`.
- `detail=true` without `detail_format` still requests XML serializer.
- `detail=true&detail_format=xml` requests XML serializer.
- `detail=true&detail_format=json` requests JSON serializer.
- compact requests still pass `detail=False` and no JSON format.

RPC tests:

- `DecisionEngineAPI.get_data_model_info()` forwards `detail_format`.
- default `detail_format=None` is preserved for existing callers.

Endpoint tests:

- compact response uses `to_list()`.
- XML detail response uses `to_string()`.
- JSON detail response uses `to_dict()` or the chosen JSON serializer name.
- missing model still returns `{"context": []}` for all detail formats.

Model serializer tests:

- compute nodes are represented with the explicit node/resource fields.
- instances are nested under their mapped compute node.
- unmapped instances are represented under `unmapped_instances`.
- output ordering is stable.
- storage and baremetal serializers are not exposed through REST unless their
  data model types are enabled.

Docs checks:

- api-ref builds with warnings as errors.
- releasenotes build with warnings as errors.

## Risks

The main risk is freezing an accidental internal data shape as public API.
Mitigation: use explicit allowlists and a schema envelope instead of dumping
object dictionaries or graph data.

Another risk is confusing XML and JSON detail behavior. Mitigation: keep XML
as the default detail serializer and require explicit `detail_format=json` for
the new shape.

## Decision

Proceed with API microversion `1.8`, `detail_format=json`, a future-safe JSON
envelope, and compute implementation first. Reserve storage and baremetal
schema sections for future work, but do not expose those model types in REST
as part of this change.
