import requests_mock

from eset_modules import EsetModule
from eset_modules.action_deisolate_endpoint import EsetDeIsolateEndpointAction
from eset_modules.action_isolate_endpoint import EsetIsolateEndpointAction
from eset_modules.action_scan import EsetScanAction


def test_action_isolate():
    args = {"device_uuids": ["1111-2222-3333-4444"]}
    with requests_mock.Mocker() as mock_requests:
        module = EsetModule()
        module.configuration = {"region": "eu", "username": "johndoe", "password": "qwerty"}

        mock_requests.post(
            "https://eu.business-account.iam.eset.systems/oauth/token",
            json={
                "access_token": "foo-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.post(
            "https://eu.automation.eset.systems/v1/device_tasks",
            json={
                "task": {
                    "uuid": "987439d1-fa81-4330-b9db-7a02d68f08b2",
                    "versionId": "800",
                    "displayName": "IsolateDevice",
                    "description": "IsolateDeviceASAP",
                    "action": {"name": "StartNetworkIsolation"},
                    "targets": {"devicesUuids": ["1111-2222-3333-4444"], "deviceGroupsUuids": []},
                    "triggers": [{"manual": {"expireTime": "2025-01-13T15:34:36Z"}}],
                    "source": "DEVICE_TASK_SOURCE_UNSPECIFIED",
                    "assetGroupUuid": "",
                }
            },
        )
        action = EsetIsolateEndpointAction(module)
        action.run(args)


def test_action_deisolate():
    args = {"device_uuids": ["1111-2222-3333-4444"]}
    with requests_mock.Mocker() as mock_requests:
        module = EsetModule()
        module.configuration = {"region": "eu", "username": "johndoe", "password": "qwerty"}

        mock_requests.post(
            "https://eu.business-account.iam.eset.systems/oauth/token",
            json={
                "access_token": "foo-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.post(
            "https://eu.automation.eset.systems/v1/device_tasks",
            json={
                "task": {
                    "uuid": "53572782-9a05-4b92-a8e7-ed287fc66aaa",
                    "versionId": "809",
                    "displayName": "DeIsolateDevice",
                    "description": "DeIsolateDeviceASAP",
                    "action": {"name": "EndNetworkIsolation"},
                    "targets": {"devicesUuids": ["1111-2222-3333-4444"], "deviceGroupsUuids": []},
                    "triggers": [{"manual": {"expireTime": "2025-01-13T15:36:00Z"}}],
                    "source": "DEVICE_TASK_SOURCE_UNSPECIFIED",
                    "assetGroupUuid": "",
                }
            },
        )
        action = EsetDeIsolateEndpointAction(module)
        action.run(args)


def test_eset_scan_action():
    args = {
        "device_uuids": ["1111-2222-3333-4444"],
        "scan_profile": "Smart",
        "cleaning_enabled": False,
        "shutdown_enabled": False,
    }
    with requests_mock.Mocker() as mock_requests:
        module = EsetModule()
        module.configuration = {"region": "eu", "username": "johndoe", "password": "qwerty"}

        mock_requests.post(
            "https://eu.business-account.iam.eset.systems/oauth/token",
            json={
                "access_token": "foo-token",
                "token_type": "Bearer",
                "expires_in": 1799,
            },
        )

        mock_requests.post(
            "https://eu.automation.eset.systems/v1/device_tasks",
            json={
                "task": {
                    "uuid": "4f72ac71-121e-46ea-9092-34b8e12a845c",
                    "versionId": "813",
                    "displayName": "ScanAll",
                    "description": "OnDemandScanASAP",
                    "action": {
                        "name": "OnDemandScan",
                        "params": {
                            "@type": "type.googleapis.com/Era.Common.DataDefinition.Task.ESS.OnDemandScan",
                            "scanProfile": "Smart",
                            "scanTargets": [],
                            "cleaningEnabled": False,
                            "shutdownEnabled": False,
                        },
                    },
                    "targets": {"devicesUuids": ["1111-2222-3333-4444"], "deviceGroupsUuids": []},
                    "triggers": [{"manual": {"expireTime": "2025-01-13T15:37:37Z"}}],
                    "source": "DEVICE_TASK_SOURCE_UNSPECIFIED",
                    "assetGroupUuid": "",
                }
            },
        )
        action = EsetScanAction(module)
        action.run(args)
