# -*- encoding: utf-8 -*-
# Copyright (c) 2019 ZTE Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
An Interface for users and admin to List Data Model.
"""

import pecan
from pecan import rest
from wsme import types as wtypes
import wsmeext.pecan as wsme_pecan

from watcher._i18n import _
from watcher.api.controllers.v1 import types
from watcher.api.controllers.v1 import utils
from watcher.common import exception
from watcher.common import policy
from watcher.decision_engine import rpcapi


_TRUE_VALUES = ('true', '1')
_FALSE_VALUES = ('false', '0')
_DETAIL_FORMAT_JSON = 'json'
_DETAIL_FORMAT_XML = 'xml'
_DETAIL_FORMATS = (_DETAIL_FORMAT_JSON, _DETAIL_FORMAT_XML)


def _is_set(value):
    return value is not None and value is not wtypes.Unset


def _parse_detail(detail):
    if not _is_set(detail):
        return False

    value = detail.lower()
    if value in _TRUE_VALUES:
        return True
    if value in _FALSE_VALUES:
        return False

    raise exception.Invalid(
        _('Invalid boolean value for detail: %s. Acceptable values are '
          'true, false, 1, or 0.') % detail)


def _parse_detail_format(detail_format):
    if not _is_set(detail_format):
        return None

    value = detail_format.lower()
    if value in _DETAIL_FORMATS:
        return value

    raise exception.Invalid(
        _('Invalid detail_format value: %s. Acceptable values are '
          'json or xml.') % detail_format)


class DataModelController(rest.RestController):
    """REST controller for data model"""

    def __init__(self):
        super(DataModelController, self).__init__()

    from_data_model = False
    """A flag to indicate if the requests to this controller are coming
    from the top-level resource DataModel."""

    @wsme_pecan.wsexpose(wtypes.text, wtypes.text, types.uuid, wtypes.text,
                         wtypes.text)
    def get_all(self, data_model_type='compute', audit_uuid=None,
                detail=None, detail_format=None):
        """Retrieve information about the given data model.

        :param data_model_type: The type of data model user wants to list.
                                Supported values: compute.
                                Future support values: storage, baremetal.
                                The default value is compute.
        :param audit_uuid: The UUID of the audit,  used to filter data model
                           by the scope in audit.
        :param detail: Whether to return detailed data model information.
        :param detail_format: Optional detailed output format, ``xml`` or
                              ``json``. Requires ``detail=true``.
        """
        if not utils.allow_list_datamodel():
            raise exception.NotAcceptable
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
        if self.from_data_model:
            raise exception.OperationNotPermitted
        allowed_data_model_type = [
            'compute',
            ]
        if data_model_type not in allowed_data_model_type:
            raise exception.DataModelTypeNotFound(
                data_model_type=data_model_type)
        context = pecan.request.context
        de_client = rpcapi.DecisionEngineAPI()
        policy.enforce(context, 'data_model:get_all',
                       action='data_model:get_all')
        rpc_kwargs = {'detail': detail}
        if detail_format is not None:
            rpc_kwargs['detail_format'] = detail_format
        rpc_all_data_model = de_client.get_data_model_info(
            context,
            data_model_type,
            audit_uuid,
            **rpc_kwargs)
        return rpc_all_data_model
