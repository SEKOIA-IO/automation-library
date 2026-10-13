import json
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import requests_mock
from sekoia_automation.storage import PersistentJSON

from microsoft_ad.asset_connectors.user_assets import MicrosoftADUserAssetConnector
from microsoft_ad.asset_connectors.user_assets_action import MicrosoftADUserAssetsOnPremiseAction
from microsoft_ad.models.common_models import MicrosoftADModule

MODULE_PATH = Path(__file__).parents[2]
UUID = "04716e25-c97f-4a22-925e-8b636ad9c8a4"
PUSH_URL = f"https://api.example.com/api/v2/asset-management/asset-connector/{UUID}"
LOGS_URL = f"https://api.example.com/api/v1/symphony/connector-configurations/{UUID}/logs"


def test_connector_manifest_declares_the_on_premise_action():
    connector = json.loads((MODULE_PATH / "connector_microsoftad_user_assets.json").read_text())
    action = json.loads((MODULE_PATH / "action_collect_user_assets_on_premise.json").read_text())

    assert connector["execution_modes"] == ["cloud", "on_premise"]
    assert connector["on_premise_action"] == action["uuid"]
    assert action["internal"] is True
    assert {"asset_connector_uuid", "connector_configuration_token"} <= set(action["arguments"]["required"])


def test_run_pushes_ad_users_to_the_asset_connector(tmp_path):
    module = MicrosoftADModule()
    module.configuration = {"servername": "ad.example.com", "admin_username": "admin", "admin_password": "password"}
    action = MicrosoftADUserAssetsOnPremiseAction(module=module, data_path=tmp_path)
    entries = [
        {
            "dn": "CN=Jane Doe,DC=example,DC=com",
            "attributes": {
                "userPrincipalName": "jane@example.com",
                "objectSid": "S-1-5-21-1",
                "whenCreated": datetime(2024, 6, 1),
            },
        }
    ]

    with (
        patch.object(MicrosoftADUserAssetConnector, "_run_paged_search", return_value=iter(entries)),
        requests_mock.Mocker() as api,
    ):
        api.post(PUSH_URL, json={})
        api.post(LOGS_URL)

        results = action.run(
            {
                "asset_connector_uuid": UUID,
                "connector_configuration_token": "configuration-token",
                "sekoia_base_url": "https://api.example.com",
                "sekoia_api_key": "api-key",
                "batch_size": 1000,
                "basedn": "DC=example,DC=com",
            }
        )

    assert results == {"fetched": 1, "pushed_batches": 1, "failed_batches": 0, "has_more": False}
    pushes = [request for request in api.request_history if request.url == PUSH_URL]
    assert [item["user"]["uid"] for item in pushes[0].json()["items"]] == ["S-1-5-21-1"]
    assert any(request.url == LOGS_URL for request in api.request_history)
    with PersistentJSON("context.json", tmp_path) as cache:
        assert cache["most_recent_datetime"] == "20240601000000.0Z"
