.. -*- rst -*-

==========
Data Model
==========

.. versionadded:: 1.3

``Data Model`` is very important for Watcher to generate resource
optimization solutions. Users can easily view the data model by the
API.

.. versionchanged:: 1.7

   Added the optional ``detail`` query parameter. The default compact
   response is unchanged. When ``detail=true`` is requested, the ``context``
   response field contains the stable XML representation of the data model.

.. versionchanged:: 1.8

   Added the optional ``detail_format`` query parameter for detailed data model
   responses. When ``detail=true&detail_format=json`` is requested and a data
   model is available, the ``context`` response field contains the stable JSON
   detail object. Omitting ``detail_format`` or requesting
   ``detail_format=xml`` keeps the existing XML detail behavior.


List Data Model
===============

.. rest_method::  GET /v1/data_model

Returns the information about Data Model.

Normal response codes: 200

Error codes: 400,401,406

Request
-------

.. rest_parameters:: parameters.yaml

   - data_model_type: r_data_model_type
   - audit_uuid: r_audit_uuid
   - detail: r_data_model_detail
   - detail_format: r_data_model_detail_format

Response
--------

.. rest_parameters:: parameters.yaml

    - context: data_model_context
    - server_uuid: server_uuid
    - server_name: server_name
    - server_vcpus: server_vcpus
    - server_memory: server_memory
    - server_disk: server_disk
    - server_state: server_state
    - node_uuid: node_uuid
    - node_hostname: node_hostname
    - node_vcpus: node_vcpus
    - node_vcpu_ratio: node_vcpu_ratio
    - node_memory: node_memory
    - node_memory_ratio: node_memory_ratio
    - node_disk: node_disk
    - node_disk_ratio: node_disk_ratio
    - node_state: node_state

**Example JSON representation of a Data Model:**

.. literalinclude:: samples/datamodel-list-response.json
   :language: javascript

**Example JSON representation of an XML detailed Data Model:**

.. literalinclude:: samples/datamodel-list-detail-response.json
   :language: javascript

**Example JSON representation of a JSON detailed Data Model:**

.. literalinclude:: samples/datamodel-list-json-detail-response.json
   :language: javascript
