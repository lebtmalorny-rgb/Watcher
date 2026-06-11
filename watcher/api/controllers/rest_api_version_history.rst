REST API Version History
========================

This documents the changes made to the REST API with every
microversion change. The description for each version should be a
verbose one which has enough information to be suitable for use in
user documentation.

1.0 (Initial version)
-----------------------
This is the initial version of the Watcher API which supports
microversions.

A user can specify a header in the API request::

  OpenStack-API-Version: infra-optim <version>

where ``<version>`` is any valid api version for this API.

If no version is specified then the API will behave as if version 1.0
was requested.

1.1
---
Added the parameters ``start_time`` and ``end_time`` to
create audit request. Supported for start and end time of continuous
audits.

1.2
---
Added ``force`` into create audit request. If ``force`` is true,
audit will be executed despite of ongoing actionplan.

1.3
---
Added list data model API.

1.4
---
Added Watcher webhook API. It can be used to trigger audit
with ``event`` type.

1.5
---
Added a dedicated action plan cancel API::

  POST /v1/action_plans/{action_plan_uuid}/cancel

This endpoint keeps the existing cancel state transitions without requiring
clients to build a JSON Patch request.

1.6
---
Added ``audit_template_uuid`` to Audit response bodies. The field is exposed
for Audit resources created from an Audit Template and is ``null`` when there
is no associated Audit Template. The internal numeric ``audit_template_id``
is not exposed by the REST API.

1.7
---
Added the optional ``detail`` query parameter to the Data Model API::

  GET /v1/data_model?detail=true

When ``detail`` is omitted or false, the API keeps the existing compact
``context`` list response. When ``detail`` is true, ``context`` contains the
stable XML representation produced by the data model serializer.

1.8
---
Added the optional ``detail_format`` query parameter to the Data Model API::

  GET /v1/data_model?detail=true&detail_format=json

When ``detail_format=json`` is requested with ``detail=true`` and a data model
is available, ``context`` contains the stable JSON data model detail object.
Omitting ``detail_format`` or requesting ``detail_format=xml`` keeps the
existing XML detail behavior.
