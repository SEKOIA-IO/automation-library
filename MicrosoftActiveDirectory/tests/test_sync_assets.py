import json
import os
import signal
from collections.abc import Callable, Generator
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
import requests
import requests_mock
from ldap3.core.exceptions import LDAPException
from pydantic.v1 import ValidationError
from sekoia_automation.asset_connector.models.ocsf.user import UserOCSFModel
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.trigger import Trigger
from tenacity import wait_none

from microsoft_ad.actions_base import MicrosoftADModule
from microsoft_ad.asset_connectors.exceptions import AssetConnectorCriticalError
from microsoft_ad.asset_connectors.user_assets import MicrosoftADUserAssetConnector
from microsoft_ad.asset_connectors.user_assets_sync import MicrosoftADUserAssetSyncConnector
from microsoft_ad.client.ldap_client import LDAPClient
from microsoft_ad.sync_assets_actions import SynchronizeAssetsAction

MODULE_PATH = Path(__file__).parents[1]
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


def build_entry(sid: str, created: datetime) -> dict[str, Any]:
    """Build a minimal fake LDAP user entry."""
    return {
        "dn": f"CN={sid},DC=example,DC=com",
        "attributes": {
            "userPrincipalName": f"{sid}@example.com",
            "objectSid": sid,
            "member_of": [],
            "whenCreated": created,
        },
    }


def build_user_model(sid: str) -> UserOCSFModel:
    """Map a minimal fake LDAP entry to an OCSF user model."""
    connector = object.__new__(MicrosoftADUserAssetConnector)
    return connector.map_user_fields(build_entry(sid, datetime(2024, 1, 1, 12, 0, 0)))


def fake_directory(entries: list[dict[str, Any]]) -> Callable[[MicrosoftADUserAssetConnector], Any]:
    """
    Fake `_run_paged_search`: return the entries in directory order (not sorted by
    `whenCreated`), filtered by the stored checkpoint like the LDAP filter
    `(whenCreated>=checkpoint)`.
    """

    def run_paged_search(connector: MicrosoftADUserAssetConnector) -> Any:
        checkpoint = connector.most_recent_datetime
        return iter(
            [
                entry
                for entry in entries
                if checkpoint is None or entry["attributes"]["whenCreated"].strftime("%Y%m%d%H%M%S.0Z") >= checkpoint
            ]
        )

    return run_paged_search


def build_fake_connector(
    items: list[UserOCSFModel],
    stop_after: int | None = None,
    sigterm_after: int | None = None,
    wait_for_stop: bool = False,
    error: Exception | None = None,
    critical: str | None = None,
    ldap_client: Any = None,
) -> type[MicrosoftADUserAssetSyncConnector]:
    """Build a sync connector class whose `get_assets` yields `items` with the given behaviour."""

    class FakeSyncConnector(MicrosoftADUserAssetSyncConnector):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._ldap_client = ldap_client

        def get_assets(self) -> Generator[UserOCSFModel, None, None]:
            for index, item in enumerate(items):
                if index == stop_after:
                    self.stop()
                if index == sigterm_after:
                    os.kill(os.getpid(), signal.SIGTERM)
                if wait_for_stop:
                    self._stop_event.wait(5)
                if critical:
                    self.log(critical, level="critical")
                if error:
                    raise error
                yield item
                # Like the real connector, move the in-memory cursor once the item is consumed
                self._latest_time = f"2024010{index + 1}000000.0Z"

    return FakeSyncConnector


@pytest.fixture
def build_action(tmp_path):
    def build(**behaviour: Any) -> SynchronizeAssetsAction:
        items = behaviour.pop("items", [build_user_model(f"S-1-5-21-{i}") for i in range(3)])
        max_duration = behaviour.pop("max_duration", SynchronizeAssetsAction.MAX_DURATION)

        class FakeSyncAction(SynchronizeAssetsAction):
            connector_class = build_fake_connector(items, **behaviour)
            MAX_DURATION = max_duration

        return FakeSyncAction(MicrosoftADModule(), data_path=tmp_path)

    return build


@pytest.fixture
def api():
    with requests_mock.Mocker() as mock:
        mock.post(PUSH_URL, json={})
        mock.post(LOGS_URL)
        yield mock


def requests_to(api, url):
    return [request for request in api.request_history if request.url == url]


def sent_logs(api) -> list[dict[str, Any]]:
    return [log for request in requests_to(api, LOGS_URL) for log in request.json()["logs"]]


def read_context(path: Path) -> dict[str, Any]:
    with PersistentJSON("context.json", path) as cache:
        return dict(cache)


def test_run_pushes_assets_to_the_connector_configuration(build_action, api, tmp_path):
    results = build_action().run(ARGUMENTS)

    assert results == {"fetched": 3, "pushed_batches": 3, "failed_batches": 0, "has_more": False}
    pushes = requests_to(api, PUSH_URL)
    assert len(pushes) == 3
    assert pushes[0].headers["Authorization"] == "Bearer api-key"
    assert pushes[0].headers["User-Agent"] == f"sekoiaio-asset-connector-{UUID}"
    # The checkpoint is committed once, at the end of the complete cycle
    assert read_context(tmp_path)["most_recent_datetime"] == "20240103000000.0Z"


def test_run_sends_the_logs_to_the_connector_configuration(build_action, api):
    build_action().run(ARGUMENTS)

    logs = requests_to(api, LOGS_URL)
    assert logs
    assert logs[-1].headers["Authorization"] == "Bearer configuration-token"
    assert any("Starting a new asset fetch cycle" in log["message"] for log in sent_logs(api))


def test_run_returns_has_more_when_stopped(build_action, api, tmp_path):
    results = build_action(stop_after=1).run(ARGUMENTS)

    assert results["has_more"] is True
    assert results["pushed_batches"] == 1
    assert len(requests_to(api, PUSH_URL)) == 1
    # A stopped cycle never advances the checkpoint
    assert "most_recent_datetime" not in read_context(tmp_path)


def test_run_warns_when_the_time_limit_is_reached(build_action, api, tmp_path):
    results = build_action(wait_for_stop=True, max_duration=0.05).run(ARGUMENTS)

    assert results["has_more"] is True
    assert not requests_to(api, PUSH_URL)
    assert "most_recent_datetime" not in read_context(tmp_path)
    assert any(
        log["level"] == "warning"
        and "time limit" in log["message"]
        and "checkpoint was not advanced" in log["message"]
        for log in sent_logs(api)
    )


def test_run_returns_has_more_on_sigterm_and_restores_the_handler(build_action, api, tmp_path):
    def handler(*_):
        pass

    previous = signal.signal(signal.SIGTERM, handler)
    try:
        results = build_action(sigterm_after=1).run(ARGUMENTS)

        assert results["has_more"] is True
        assert results["pushed_batches"] == 1
        assert len(requests_to(api, PUSH_URL)) == 1
        assert "most_recent_datetime" not in read_context(tmp_path)
        assert signal.getsignal(signal.SIGTERM) is handler
    finally:
        signal.signal(signal.SIGTERM, previous)


def test_run_reports_a_failed_push(build_action, api, tmp_path):
    api.post(PUSH_URL, [{"status_code": 200, "json": {}}, {"status_code": 500, "json": {}}])

    action = build_action()
    results = action.run(ARGUMENTS)

    # The cycle stops at the first failed batch: the run ends in error and still returns its counters
    assert results == {"fetched": 2, "pushed_batches": 1, "failed_batches": 1, "has_more": False}
    assert action.error_message == "A batch of assets could not be pushed to Sekoia.io"
    assert len(requests_to(api, PUSH_URL)) == 2
    assert "most_recent_datetime" not in read_context(tmp_path)
    logs = sent_logs(api)
    assert any(log["level"] == "error" and "Error while pushing assets" in log["message"] for log in logs)
    assert any(
        log["level"] == "warning"
        and "could not be pushed" in log["message"]
        and "checkpoint was not" in log["message"]
        for log in logs
    )


def test_failed_push_sends_the_counters_with_the_error(build_action, api):
    api.post(PUSH_URL, status_code=500, json={})
    action = build_action()

    with (
        patch.object(type(action), "arguments", ARGUMENTS),
        patch.object(type(action), "set_task_as_running"),
        patch.object(type(action), "_send_request") as send_request,
    ):
        action.execute()

    # The SDK sends the results and the error in the same callback: the run fails and keeps its counters
    data = send_request.call_args.args[0]
    assert data["status"] == "finished"
    assert data["error"] == "A batch of assets could not be pushed to Sekoia.io"
    assert data["results"] == {"fetched": 1, "pushed_batches": 0, "failed_batches": 1, "has_more": False}


def test_run_reports_a_push_that_keeps_failing_to_connect(build_action, api, tmp_path):
    api.post(PUSH_URL, exc=requests.ConnectionError("connection refused"))

    with patch.object(MicrosoftADUserAssetSyncConnector, "PUSH_RETRY_MAX_DELAY", 0):
        action = build_action()
        results = action.run(ARGUMENTS)

    assert results == {"fetched": 1, "pushed_batches": 0, "failed_batches": 1, "has_more": False}
    assert action.error_message == "A batch of assets could not be pushed to Sekoia.io"
    assert "most_recent_datetime" not in read_context(tmp_path)
    assert any(log["level"] == "error" and "Unable to push a batch" in log["message"] for log in sent_logs(api))


def test_run_returns_has_more_when_stopped_during_a_push(build_action, api, tmp_path):
    def stop_then_fail(connector: MicrosoftADUserAssetSyncConnector, *_: Any) -> None:
        connector.stop()
        raise requests.ConnectionError("connection reset")

    with patch.object(MicrosoftADUserAssetSyncConnector, "post_assets_to_api", stop_then_fail):
        action = build_action()
        results = action.run(ARGUMENTS)

    assert results == {"fetched": 1, "pushed_batches": 0, "failed_batches": 0, "has_more": True}
    assert action.error_message is None
    assert "most_recent_datetime" not in read_context(tmp_path)


def test_run_logs_errors_to_the_connector_configuration(build_action, api):
    with pytest.raises(RuntimeError):
        build_action(error=RuntimeError("LDAP is down")).run(ARGUMENTS)

    assert any(log["level"] == "error" and "LDAP is down" in log["message"] for log in sent_logs(api))


def test_run_keeps_the_real_error_when_the_logs_endpoint_is_down(build_action, api):
    api.post(LOGS_URL, status_code=503)
    action = build_action(error=RuntimeError("LDAP is down"))

    # Don't wait between the SDK's retries of the logs sending
    with patch.object(Trigger._send_logs_to_api.retry, "wait", wait_none()):
        with pytest.raises(RuntimeError, match="LDAP is down"):
            action.run(ARGUMENTS)

    assert requests_to(api, LOGS_URL)
    assert any(
        log["level"] == "warning" and "Unable to send the connector error log" in log["message"]
        for log in action._logs
    )


def test_run_stops_on_a_critical_log(build_action, api, tmp_path):
    with pytest.raises(AssetConnectorCriticalError):
        build_action(critical="Invalid AD credentials").run(ARGUMENTS)

    logs = requests_to(api, LOGS_URL)
    assert logs[0].headers["Authorization"] == "Bearer configuration-token"
    assert [log["level"] for log in sent_logs(api) if log["message"] == "Invalid AD credentials"] == ["critical"]
    # The cycle stops at once: nothing pushed, checkpoint not advanced
    assert not requests_to(api, PUSH_URL)
    assert "most_recent_datetime" not in read_context(tmp_path)


def test_run_requires_the_connector_configuration(build_action, api):
    arguments = dict(ARGUMENTS)
    del arguments["connector_configuration_token"]

    with pytest.raises(ValidationError):
        build_action().run(arguments)

    assert not api.request_history


@pytest.mark.parametrize("batch_size", [0, -1])
def test_run_rejects_a_batch_size_below_one(build_action, api, batch_size):
    with pytest.raises(ValidationError):
        build_action().run({**ARGUMENTS, "batch_size": batch_size})

    assert not api.request_history


def test_run_restores_the_signal_handlers(build_action, api):
    def handler(*_):
        pass

    previous = signal.signal(signal.SIGTERM, handler)
    try:
        build_action().run(ARGUMENTS)

        assert signal.getsignal(signal.SIGTERM) is handler
    finally:
        signal.signal(signal.SIGTERM, previous)


def test_run_skips_the_signal_handlers_not_installed_from_python(build_action, api):
    def handler(*_):
        pass

    previous_sigint = signal.getsignal(signal.SIGINT)
    previous_sigterm = signal.signal(signal.SIGTERM, handler)
    real_getsignal = signal.getsignal
    try:
        # getsignal returns None for a handler installed outside Python (e.g. from C)
        with patch.object(
            signal, "getsignal", side_effect=lambda signum: None if signum == signal.SIGINT else real_getsignal(signum)
        ):
            results = build_action().run(ARGUMENTS)

        assert results == {"fetched": 3, "pushed_batches": 3, "failed_batches": 0, "has_more": False}
        assert signal.getsignal(signal.SIGTERM) is handler
    finally:
        signal.signal(signal.SIGINT, previous_sigint)
        signal.signal(signal.SIGTERM, previous_sigterm)


def test_run_closes_the_ldap_connection(build_action, api):
    ldap_client = Mock()

    build_action(ldap_client=ldap_client).run(ARGUMENTS)

    ldap_client.unbind.assert_called_once()


def test_run_ignores_errors_while_closing_the_ldap_connection(build_action, api):
    ldap_client = Mock()
    ldap_client.unbind.side_effect = LDAPException("connection already closed")

    results = build_action(ldap_client=ldap_client).run(ARGUMENTS)

    assert results["has_more"] is False
    ldap_client.unbind.assert_called_once()


def test_retry_stops_when_the_connector_is_stopped(tmp_path):
    module = MicrosoftADModule()
    connector = MicrosoftADUserAssetSyncConnector(module=module, data_path=tmp_path)
    connector.stop()
    attempts = 0

    with pytest.raises(ConnectionError):
        for attempt in connector._retry():
            with attempt:
                attempts += 1
                raise ConnectionError("Sekoia.io is unreachable")

    assert attempts == 1


def test_ldap_connection_has_a_receive_timeout():
    client = LDAPClient()
    client.module = MicrosoftADModule()
    client.module.configuration = {
        "servername": "ad.example.com",
        "admin_username": "admin",
        "admin_password": "password",
    }

    with patch("microsoft_ad.client.ldap_client.Connection") as connection:
        client._create_ldap_connection()

    assert connection.call_args.kwargs["receive_timeout"] == 120


# Tests with the real connector, only the LDAP search is faked


def build_real_action(tmp_path: Path) -> SynchronizeAssetsAction:
    module = MicrosoftADModule()
    module.configuration = {  # type: ignore[assignment]
        "servername": "ad.example.com",
        "admin_username": "admin",
        "admin_password": "password",
    }
    return SynchronizeAssetsAction(module=module, data_path=tmp_path)


def pushed_sids(api) -> list[str]:
    return [item["user"]["uid"] for request in requests_to(api, PUSH_URL) for item in request.json()["items"]]


def test_connector_manifest_declares_the_on_premise_action():
    connector = json.loads((MODULE_PATH / "connector_microsoftad_user_assets.json").read_text())
    action = json.loads((MODULE_PATH / "action_synchronize_assets.json").read_text())

    assert connector["execution_modes"] == ["cloud", "on_premise"]
    assert connector["on_premise_action"] == action["uuid"]
    assert action["internal"] is True
    assert {"asset_connector_uuid", "connector_configuration_token"} <= set(action["arguments"]["required"])
    assert "basedn" in connector["arguments"]["required"]
    assert "failed_batches" in action["results"]["properties"]
    assert action["arguments"]["properties"]["batch_size"]["default"] == 1000


def test_run_pushes_ad_users_to_the_asset_connector(tmp_path, api):
    entries = [build_entry("S-1-5-21-1", datetime(2024, 6, 1))]

    with patch.object(MicrosoftADUserAssetConnector, "_run_paged_search", fake_directory(entries)):
        results = build_real_action(tmp_path).run({**ARGUMENTS, "batch_size": 1000})

    assert results == {"fetched": 1, "pushed_batches": 1, "failed_batches": 0, "has_more": False}
    assert pushed_sids(api) == ["S-1-5-21-1"]
    assert requests_to(api, LOGS_URL)
    assert read_context(tmp_path)["most_recent_datetime"] == "20240601000000.0Z"


def test_interrupted_cycle_resumes_without_missing_users(tmp_path, api):
    # Directory order, not sorted by whenCreated: the most recent user comes second
    entries = [
        build_entry("S-1-5-21-1", datetime(2024, 1, 1)),
        build_entry("S-1-5-21-2", datetime(2025, 6, 1)),
        build_entry("S-1-5-21-3", datetime(2023, 3, 1)),
        build_entry("S-1-5-21-4", datetime(2024, 2, 1)),
    ]
    original_post = MicrosoftADUserAssetSyncConnector.post_assets_to_api
    pushes_before_stop = {"left": 2}

    def post_then_stop(connector, assets, url):
        response = original_post(connector, assets, url)
        pushes_before_stop["left"] -= 1
        if pushes_before_stop["left"] == 0:
            connector.stop()  # e.g. the time limit or a SIGTERM
        return response

    with (
        patch.object(MicrosoftADUserAssetConnector, "_run_paged_search", fake_directory(entries)),
        patch.object(MicrosoftADUserAssetSyncConnector, "post_assets_to_api", post_then_stop),
    ):
        first = build_real_action(tmp_path).run(ARGUMENTS)
        assert first["has_more"] is True
        assert pushed_sids(api) == ["S-1-5-21-1", "S-1-5-21-2"]
        assert "most_recent_datetime" not in read_context(tmp_path)

        second = build_real_action(tmp_path).run(ARGUMENTS)

    assert second["has_more"] is False
    assert set(pushed_sids(api)) == {"S-1-5-21-1", "S-1-5-21-2", "S-1-5-21-3", "S-1-5-21-4"}
    context = read_context(tmp_path)
    assert context["most_recent_datetime"] == "20250601000000.0Z"
    assert context["seen_sids_at_checkpoint"] == ["S-1-5-21-2"]


def test_run_from_an_existing_checkpoint_skips_seen_users(tmp_path, api):
    with PersistentJSON("context.json", tmp_path) as cache:
        cache["most_recent_datetime"] = "20240201000000.0Z"
        cache["seen_sids_at_checkpoint"] = ["S-1-5-21-4"]
    entries = [
        build_entry("S-1-5-21-1", datetime(2024, 1, 1)),
        build_entry("S-1-5-21-2", datetime(2025, 6, 1)),
        build_entry("S-1-5-21-3", datetime(2023, 3, 1)),
        build_entry("S-1-5-21-4", datetime(2024, 2, 1)),
        build_entry("S-1-5-21-5", datetime(2024, 2, 1)),
    ]
    original_post = MicrosoftADUserAssetSyncConnector.post_assets_to_api
    checkpoints_at_push: list[str | None] = []

    def post_and_record_checkpoint(connector, assets, url):
        response = original_post(connector, assets, url)
        checkpoints_at_push.append(connector.most_recent_datetime)
        return response

    with (
        patch.object(MicrosoftADUserAssetConnector, "_run_paged_search", fake_directory(entries)),
        patch.object(MicrosoftADUserAssetSyncConnector, "post_assets_to_api", post_and_record_checkpoint),
    ):
        results = build_real_action(tmp_path).run(ARGUMENTS)

    assert results == {"fetched": 2, "pushed_batches": 2, "failed_batches": 0, "has_more": False}
    assert pushed_sids(api) == ["S-1-5-21-2", "S-1-5-21-5"]
    # The checkpoint is not committed after each batch, only once the whole directory has been read
    assert checkpoints_at_push == ["20240201000000.0Z", "20240201000000.0Z"]
    context = read_context(tmp_path)
    assert context["most_recent_datetime"] == "20250601000000.0Z"
    assert context["seen_sids_at_checkpoint"] == ["S-1-5-21-2"]
