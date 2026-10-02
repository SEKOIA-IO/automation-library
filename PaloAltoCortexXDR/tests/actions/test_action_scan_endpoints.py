from unittest.mock import Mock

import pytest
import requests_mock

from cortex_module.actions.action_abort_scan_endpoints import AbortScanEndpointsAction
from cortex_module.actions.action_scan_endpoints import ScanEndpointsAction


@pytest.fixture
def scan_action(module, symphony_storage):
    action = ScanEndpointsAction(module=module, data_path=symphony_storage)
    action.log_exception = Mock()
    action.log = Mock()
    return action


@pytest.fixture
def abort_scan_action(module, symphony_storage):
    action = AbortScanEndpointsAction(module=module, data_path=symphony_storage)
    action.log_exception = Mock()
    action.log = Mock()
    return action


def test_run_scan_action_with_all_filters(scan_action):
    fqdn = scan_action.module.configuration.fqdn
    url = f"https://api-{fqdn}/public_api/v1/endpoints/scan"

    arguments = {
        "incident_id": "inc-001",
        "filter_endpoint_id_list": ["endpoint-01"],
        "filter_dist_name": ["ubuntu"],
        "filter_group_name": ["prod"],
        "filter_ip_list": ["10.0.0.1"],
        "filter_alias": ["host-alias"],
        "filter_hostname": ["host1"],
        "filter_platform": ["windows", "linux"],
        "filter_isolate": ["isolated"],
        "filter_scan_status": ["in_progress"],
        "filter_username": ["alice"],
    }

    expected_payload = {
        "request_data": {
            "incident_id": "inc-001",
            "filters": [
                {"field": "endpoint_id_list", "operator": "in", "value": ["endpoint-01"]},
                {"field": "dist_name", "operator": "in", "value": ["ubuntu"]},
                {"field": "group_name", "operator": "in", "value": ["prod"]},
                {"field": "ip_list", "operator": "in", "value": ["10.0.0.1"]},
                {"field": "alias", "operator": "in", "value": ["host-alias"]},
                {"field": "hostname", "operator": "in", "value": ["host1"]},
                {"field": "username", "operator": "in", "value": ["alice"]},
                {"field": "platform", "operator": "in", "value": ["windows", "linux"]},
                {"field": "isolate", "operator": "in", "value": ["isolated"]},
                {"field": "scan_status", "operator": "in", "value": ["in_progress"]},
            ],
        }
    }

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            status_code=200,
            json={"result": "ok"},
            additional_matcher=lambda request: request.json() == expected_payload,
        )

        assert scan_action.run(arguments) == {"result": "ok"}


def test_run_scan_action_without_filters(scan_action):
    fqdn = scan_action.module.configuration.fqdn
    url = f"https://api-{fqdn}/public_api/v1/endpoints/scan"

    expected_payload = {
        "request_data": {
            "filters": "all",
        }
    }

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            status_code=200,
            json={"result": "ok"},
            additional_matcher=lambda request: request.json() == expected_payload,
        )

        assert scan_action.run({}) == {"result": "ok"}


def test_run_abort_scan_action(abort_scan_action):
    fqdn = abort_scan_action.module.configuration.fqdn
    url = f"https://api-{fqdn}/public_api/v1/endpoints/abort_scan"

    arguments = {
        "filter_endpoint_id_list": ["endpoint-02"],
    }

    expected_payload = {
        "request_data": {
            "filters": [
                {"field": "endpoint_id_list", "operator": "in", "value": ["endpoint-02"]},
            ],
        }
    }

    with requests_mock.Mocker() as mock:
        mock.post(
            url,
            status_code=200,
            json={"result": "aborted"},
            additional_matcher=lambda request: request.json() == expected_payload,
        )

        assert abort_scan_action.run(arguments) == {"result": "aborted"}
