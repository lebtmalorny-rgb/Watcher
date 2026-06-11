# -*- encoding: utf-8 -*-
# Copyright 2019 ZTE Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import unittest
from unittest import mock

from watcher.common import exception
from watcher.common import utils
from watcher.decision_engine.messaging import data_model_endpoint
from watcher.decision_engine.model.collector import manager
from watcher.objects import audit


class TestDataModelEndpoint(unittest.TestCase):
    def setUp(self):
        self.endpoint_instance = data_model_endpoint.DataModelEndpoint('fake')

    def _patch_collector_model(self, available_data_model):
        collector = mock.Mock()
        latest_model = mock.Mock()
        audit_scope_handler = mock.Mock()
        collector.get_latest_cluster_data_model.return_value = latest_model
        collector.get_audit_scope_handler.return_value = audit_scope_handler
        audit_scope_handler.get_scoped_model.return_value = \
            available_data_model

        collector_manager = mock.Mock()
        collector_manager.get_cluster_model_collector.return_value = collector
        patcher = mock.patch.object(
            manager, 'CollectorManager', return_value=collector_manager)
        patcher.start()
        self.addCleanup(patcher.stop)

        return collector_manager, collector, audit_scope_handler, latest_model

    @mock.patch.object(audit.Audit, 'get')
    def test_get_audit_scope(self, mock_get):
        mock_get.return_value = mock.Mock(scope='fake_scope')
        audit_uuid = utils.generate_uuid()

        result = self.endpoint_instance.get_audit_scope(
            context=None,
            audit=audit_uuid)
        self.assertEqual('fake_scope', result)

    @mock.patch.object(audit.Audit, 'get_by_name')
    def test_get_audit_scope_with_error_name(self, mock_get_by_name):
        mock_get_by_name.side_effect = exception.AuditNotFound()
        audit_name = 'error_audit_name'

        self.assertRaises(
            exception.InvalidIdentity,
            self.endpoint_instance.get_audit_scope,
            context=None,
            audit=audit_name)

    def test_get_data_model_info(self):
        available_model = mock.Mock()
        available_model.to_list.return_value = []
        self._patch_collector_model(available_model)

        result = self.endpoint_instance.get_data_model_info(context='fake')
        self.assertIn('context', result)

    def test_get_data_model_info_uses_compact_serializer_by_default(self):
        available_model = mock.Mock()
        available_model.to_list.return_value = [{'server_uuid': 'server'}]
        self._patch_collector_model(available_model)

        result = self.endpoint_instance.get_data_model_info(context='fake')

        self.assertEqual({'context': [{'server_uuid': 'server'}]}, result)
        available_model.to_list.assert_called_once_with()
        available_model.to_string.assert_not_called()

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

    def test_get_data_model_info_returns_empty_context_without_model(self):
        self._patch_collector_model(None)

        result = self.endpoint_instance.get_data_model_info(
            context='fake', detail=True)

        self.assertEqual({'context': []}, result)

    def test_get_data_model_info_returns_empty_context_for_json_without_model(
            self):
        self._patch_collector_model(None)

        result = self.endpoint_instance.get_data_model_info(
            context='fake', detail=True, detail_format='json')

        self.assertEqual({'context': []}, result)
