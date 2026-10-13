import signal
from collections.abc import Generator
from datetime import datetime

import pytest
import requests_mock
from pydantic.v1 import ValidationError
from sekoia_automation.asset_connector.models.ocsf.user import UserOCSFModel
from sekoia_automation.storage import PersistentJSON

from microsoft_ad.actions_base import MicrosoftADModule
from microsoft_ad.asset_connectors.exceptions import AssetConnectorPushError
from microsoft_ad.asset_connectors.user_assets import MicrosoftADUserAssetConnector
from microsoft_ad.asset_connectors.user_assets_sync import MicrosoftADUserAssetSyncConnector
from microsoft_ad.sync_assets_actions import SynchronizeAssetsAction

UUID = "04716e25-c97f-4a22-925e-8b636ad9c8a4"
BASE_URL = "https://api.sekoia.io"
PUSH_URL = f"{BASE_URL}/api/v2/asset-management/asset-connector/{UUID}"
LOGS_URL = f"{BASE_URL}/api/v1/symphony/connector-configurations/{UUID}/logs"

ARGUMENTS = {
    "asset_connector_uuid": UUID,
    "connector_configuration_token": "configuration-token",
    "sekoia_base_url": BASE_URL,
    "sekoia_api_key": "api-key",
    "basedn": "DC=example,DC=com",
    "batch_size": 1,
}


def build_user_model(sid: str) -> UserOCSFModel:
    """Map a minimal fake LDAP entry to an OCSF user model."""
    connector = object.__new__(MicrosoftADUserAssetConnector)
    entry = {
        "attributes": {
            "userPrincipalName": f"{sid}@example.com",
            "objectSid": sid,
            "member_of": [],
            "whenCreated": datetime(2024, 1, 1, 12, 0, 0),
        }
    }
    return connector.map_user_fields(entry)


class FakeSyncConnector(MicrosoftADUserAssetSyncConnector):
    items: list[UserOCSFModel] = []
    stop_after: int | None = None
    error: Exception | None = None
    critical: str | None = None

    def update_checkpoint(self) -> None:
        with PersistentJSON("context.json", self._data_path) as cache:
            cache["pushes"] = cache.get("pushes", 0) + 1

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        for index, item in enumerate(self.items):
            if index == self.stop_after:
                self.stop()
            if self.critical:
                self.log(self.critical, level="critical")
            if self.error:
                raise self.error
            yield item


class FakeSyncAction(SynchronizeAssetsAction):
    connector_class = FakeSyncConnector


@pytest.fixture
def fake_connector():
    FakeSyncConnector.items = [build_user_model(f"S-1-5-21-{i}") for i in range(3)]
    yield FakeSyncConnector
    FakeSyncConnector.items = []
    FakeSyncConnector.stop_after = None
    FakeSyncConnector.error = None
    FakeSyncConnector.critical = None


@pytest.fixture
def action(tmp_path, fake_connector):
    return FakeSyncAction(MicrosoftADModule(), data_path=tmp_path)


@pytest.fixture
def api():
    with requests_mock.Mocker() as mock:
        mock.post(PUSH_URL, json={})
        mock.post(LOGS_URL)
        yield mock


def requests_to(api, url):
    return [request for request in api.request_history if request.url == url]


def test_run_pushes_assets_to_the_connector_configuration(action, api, tmp_path):
    results = action.run(ARGUMENTS)

    assert results == {
        "fetched": 3,
        "pushed_batches": 3,
        "failed_batches": 0,
        "has_more": False,
    }
    pushes = requests_to(api, PUSH_URL)
    assert len(pushes) == 3
    assert pushes[0].headers["Authorization"] == "Bearer api-key"
    assert pushes[0].headers["User-Agent"] == f"sekoiaio-asset-connector-{UUID}"
    with PersistentJSON("context.json", tmp_path) as cache:
        assert cache["pushes"] == 3


def test_run_sends_the_logs_to_the_connector_configuration(action, api):
    action.run(ARGUMENTS)

    logs = requests_to(api, LOGS_URL)
    assert logs
    assert logs[-1].headers["Authorization"] == "Bearer configuration-token"
    messages = [log["message"] for request in logs for log in request.json()["logs"]]
    assert any("Starting a new asset fetch cycle" in message for message in messages)


def test_run_returns_has_more_when_stopped(action, api, fake_connector):
    fake_connector.stop_after = 1

    results = action.run(ARGUMENTS)

    assert results["has_more"] is True
    assert results["pushed_batches"] == 1
    assert len(requests_to(api, PUSH_URL)) == 1


def test_run_fails_on_a_failed_push(action, api, tmp_path):
    api.post(PUSH_URL, [{"status_code": 200, "json": {}}, {"status_code": 500, "json": {}}])

    with pytest.raises(AssetConnectorPushError):
        action.run(ARGUMENTS)

    assert len(requests_to(api, PUSH_URL)) == 2
    with PersistentJSON("context.json", tmp_path) as cache:
        assert cache["pushes"] == 1


def test_run_logs_errors_to_the_connector_configuration(action, api, fake_connector):
    fake_connector.error = RuntimeError("LDAP is down")

    with pytest.raises(RuntimeError):
        action.run(ARGUMENTS)

    logs = [log for request in requests_to(api, LOGS_URL) for log in request.json()["logs"]]
    assert any(log["level"] == "error" and "LDAP is down" in log["message"] for log in logs)


def test_run_sends_critical_logs_to_the_connector_configuration(action, api, fake_connector):
    fake_connector.critical = "Invalid AD credentials"

    action.run(ARGUMENTS)

    logs = requests_to(api, LOGS_URL)
    assert logs[0].headers["Authorization"] == "Bearer configuration-token"
    sent = [log for request in logs for log in request.json()["logs"]]
    # Only the first critical log keeps its level, the next ones are downgraded to error (and deduplicated)
    assert [log["level"] for log in sent if log["message"] == "Invalid AD credentials"] == ["critical", "error"]


def test_run_requires_the_connector_configuration(action, api):
    arguments = dict(ARGUMENTS)
    del arguments["connector_configuration_token"]

    with pytest.raises(ValidationError):
        action.run(arguments)

    assert not api.request_history


def test_run_restores_the_signal_handlers(action, api):
    def handler(*_):
        pass

    previous = signal.signal(signal.SIGTERM, handler)
    try:
        action.run(ARGUMENTS)

        assert signal.getsignal(signal.SIGTERM) is handler
    finally:
        signal.signal(signal.SIGTERM, previous)
