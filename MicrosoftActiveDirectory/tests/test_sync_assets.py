import json
import os
import re
import signal
import time
from collections.abc import Callable, Generator
from datetime import datetime
from pathlib import Path
from threading import Timer
from typing import Any
from unittest.mock import Mock, patch

import pytest
import requests
import requests_mock
from ldap3.core.exceptions import LDAPException
from ldap3.extend.standard.PagedSearch import paged_search_generator
from pydantic.v1 import ValidationError
from sekoia_automation.asset_connector.models.ocsf.user import UserOCSFModel
from sekoia_automation.storage import PersistentJSON
from sekoia_automation.trigger import Trigger
from tenacity import wait_fixed, wait_none

from microsoft_ad.actions_base import MicrosoftADModule
from microsoft_ad.asset_connectors.exceptions import (
    AssetConnectorCriticalError,
    AssetConnectorSearchError,
    RetryableStatusError,
)
from microsoft_ad.asset_connectors.user_assets import MicrosoftADUserAssetConnector
from microsoft_ad.asset_connectors.user_assets_sync import PAGED_RESULTS_CONTROL_OID, MicrosoftADUserAssetSyncConnector
from microsoft_ad.client.ldap_client import LDAPClient
from microsoft_ad.helpers import SORT_REQUEST_CONTROL_OID, sort_control
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


class FakeDirectory:
    """
    Fake LDAP connection: `search` answers one page of the entries matching the checkpoint
    filter `(whenCreated>=checkpoint)`, in directory order (not sorted by `whenCreated`),
    with a paged results cookie. With the sort control, sort them by `whenCreated`, or refuse
    it like a directory that cannot sort (`sorts=False`). With `error_after`, answer the page
    starting at that entry with an error result. `page_size` sends smaller pages than asked,
    which RFC 2696 allows.

    `extend.standard.paged_search` runs the real ldap3 paged search over these pages.
    """

    raise_exceptions = False
    check_names = False
    auto_referrals = False

    def __init__(
        self,
        entries: list[dict[str, Any]],
        sorts: bool = True,
        error_after: int | None = None,
        page_size: int | None = None,
    ) -> None:
        self.entries = entries
        self.sorts = sorts
        self.error_after = error_after
        self.page_size = page_size
        self.searches: list[dict[str, Any]] = []
        self.cookie_filters: dict[bytes, str] = {}
        self.response: list[dict[str, Any]] | None = None
        self.result: dict[str, Any] = {}
        self.strategy = Mock(sync=True, thread_safe=False)
        self.extend = Mock()
        self.extend.standard.paged_search = self._ldap3_paged_search

    def _ldap3_paged_search(self, generator: bool = True, **kwargs: Any) -> Any:
        return paged_search_generator(self, **kwargs)

    def _answer(self, code: int, description: str, page: list[dict[str, Any]], cookie: bytes = b"") -> bool:
        self.response = page
        self.result = {
            "result": code,
            "description": description,
            "referrals": None,
            "controls": {PAGED_RESULTS_CONTROL_OID: {"value": {"cookie": cookie}}} if code == 0 else {},
        }
        return code == 0

    def search(
        self,
        search_base: str,
        search_filter: str,
        search_scope: Any = None,
        dereference_aliases: Any = None,
        attributes: Any = None,
        size_limit: int = 0,
        time_limit: int = 0,
        types_only: bool = False,
        get_operational_attributes: bool = False,
        controls: Any = None,
        paged_size: int = 0,
        paged_criticality: bool = False,
        paged_cookie: bytes | None = None,
    ) -> bool:
        self.searches.append({"search_filter": search_filter, "controls": controls, "paged_cookie": paged_cookie})
        match = re.search(r"whenCreated>=([0-9.]+Z)", search_filter)
        checkpoint = match.group(1) if match else None
        matching = [
            entry
            for entry in self.entries
            if checkpoint is None or entry["attributes"]["whenCreated"].strftime("%Y%m%d%H%M%S.0Z") >= checkpoint
        ]
        if any(control[0] == SORT_REQUEST_CONTROL_OID for control in controls or []):
            if not self.sorts:
                return self._answer(12, "unavailableCriticalExtension", [])
            matching.sort(key=lambda entry: entry["attributes"]["whenCreated"])

        # Like a real server: a cookie only goes on the search it was issued for
        if paged_cookie and self.cookie_filters.get(paged_cookie) != search_filter:
            return self._answer(53, "unwillingToPerform", [])
        start = int(paged_cookie or 0)
        if self.error_after is not None and start >= self.error_after:
            return self._answer(51, "busy", [])
        end = start + (self.page_size or paged_size)
        cookie = str(end).encode() if end < len(matching) else b""
        self.cookie_filters[cookie] = search_filter
        return self._answer(0, "success", matching[start:end], cookie)

    def unbind(self) -> None:
        pass


def fake_directory(entries: list[dict[str, Any]], **behaviour: Any) -> Any:
    """Patch the LDAP connections of the connectors with a `FakeDirectory`."""
    return patch.object(LDAPClient, "_create_ldap_connection", return_value=FakeDirectory(entries, **behaviour))


def build_fake_connector(
    items: list[UserOCSFModel],
    stop_after: int | None = None,
    sigterm_after: int | None = None,
    wait_for_stop: bool = False,
    error: Exception | None = None,
    critical: str | None = None,
    ldap_client: Any = None,
    sorted_search: bool = True,
) -> type[MicrosoftADUserAssetSyncConnector]:
    """Build a sync connector class whose `get_assets` yields `items` with the given behaviour.

    `sorted_search` tells whether the directory accepted the sort, like `_run_paged_search` does.
    """

    class FakeSyncConnector(MicrosoftADUserAssetSyncConnector):
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._ldap_client = ldap_client

        def get_assets(self) -> Generator[UserOCSFModel, None, None]:
            self.sorted_search = sorted_search
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


@pytest.mark.parametrize(
    "sorted_search, resume",
    [
        (True, "resumes from the last pushed batch"),
        # Without the sort the checkpoint does not move: an immediate re-run would only redo the same work
        (False, "checkpoint was not advanced"),
    ],
)
def test_run_warns_when_the_time_limit_is_reached(build_action, api, tmp_path, sorted_search, resume):
    results = build_action(wait_for_stop=True, max_duration=0.05, sorted_search=sorted_search).run(ARGUMENTS)

    assert results["has_more"] is sorted_search
    assert not requests_to(api, PUSH_URL)
    assert "most_recent_datetime" not in read_context(tmp_path)
    assert any(
        log["level"] == "warning" and "time limit" in log["message"] and resume in log["message"]
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
    api.post(PUSH_URL, [{"status_code": 200, "json": {}}, {"status_code": 400, "json": {}}])

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
    api.post(PUSH_URL, status_code=400, json={})
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
    assert data["results"] == {
        "fetched": 1,
        "pushed_batches": 0,
        "failed_batches": 1,
        "has_more": False,
    }


@pytest.fixture
def fast_retries():
    """Retry the pushes without waiting, for at most half a second."""
    with (
        patch("microsoft_ad.asset_connectors.user_assets_sync.wait_exponential", return_value=wait_none()),
        patch.object(MicrosoftADUserAssetSyncConnector, "PUSH_RETRY_MAX_DELAY", 0.5),
    ):
        yield


@pytest.mark.parametrize("status_code", [408, 429, 500, 503])
def test_run_retries_a_transient_error_answer(build_action, api, fast_retries, status_code):
    api.post(PUSH_URL, [{"status_code": status_code, "json": {}}, {"status_code": 200, "json": {}}])
    action = build_action()

    results = action.run(ARGUMENTS)

    assert results == {"fetched": 3, "pushed_batches": 3, "failed_batches": 0, "has_more": False}
    assert len(requests_to(api, PUSH_URL)) == 4
    assert action.error_message is None


def test_run_fails_after_retrying_a_lasting_transient_error(build_action, api, fast_retries, tmp_path):
    api.post(PUSH_URL, status_code=503, json={})
    action = build_action()

    results = action.run(ARGUMENTS)

    assert results == {"fetched": 1, "pushed_batches": 0, "failed_batches": 1, "has_more": False}
    assert len(requests_to(api, PUSH_URL)) > 1
    assert action.error_message == "A batch of assets could not be pushed to Sekoia.io"
    assert "most_recent_datetime" not in read_context(tmp_path)


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 413])
def test_run_does_not_retry_a_client_error_answer(build_action, api, fast_retries, status_code):
    api.post(PUSH_URL, status_code=status_code, json={})
    action = build_action()

    results = action.run(ARGUMENTS)

    assert results == {"fetched": 1, "pushed_batches": 0, "failed_batches": 1, "has_more": False}
    assert len(requests_to(api, PUSH_URL)) == 1
    assert action.error_message == "A batch of assets could not be pushed to Sekoia.io"


def test_run_reports_a_push_that_keeps_failing_to_connect(build_action, api, tmp_path):
    api.post(PUSH_URL, exc=requests.ConnectionError("connection refused"))

    with patch.object(MicrosoftADUserAssetSyncConnector, "PUSH_RETRY_MAX_DELAY", 0):
        action = build_action()
        results = action.run(ARGUMENTS)

    assert results == {"fetched": 1, "pushed_batches": 0, "failed_batches": 1, "has_more": False}
    assert action.error_message == "A batch of assets could not be pushed to Sekoia.io"
    assert "most_recent_datetime" not in read_context(tmp_path)
    assert any(log["level"] == "error" and "Unable to push a batch" in log["message"] for log in sent_logs(api))


@pytest.mark.parametrize(
    "push_answer",
    [
        {"exc": requests.ConnectionError("connection refused")},
        # The SDK sends its own error log for an error answer: it raises too when the logs endpoint is down
        {"status_code": 400, "json": {"message": "bad request", "code": "E400"}},
    ],
)
def test_run_reports_the_failed_push_when_the_logs_endpoint_is_down(build_action, api, tmp_path, push_answer):
    api.post(PUSH_URL, **push_answer)
    api.post(LOGS_URL, status_code=503)

    # Don't wait between the SDK's retries of the logs sending
    with (
        patch.object(MicrosoftADUserAssetSyncConnector, "PUSH_RETRY_MAX_DELAY", 0),
        patch.object(Trigger._send_logs_to_api.retry, "wait", wait_none()),
    ):
        action = build_action()
        results = action.run(ARGUMENTS)

    assert results == {"fetched": 1, "pushed_batches": 0, "failed_batches": 1, "has_more": False}
    assert action.error_message == "A batch of assets could not be pushed to Sekoia.io"
    assert "most_recent_datetime" not in read_context(tmp_path)


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


def test_run_returns_has_more_when_the_time_limit_stops_a_push_that_times_out(build_action, api, tmp_path):
    # The SDK catches the timeout and returns None once the retries give up on the stop
    api.post(PUSH_URL, exc=requests.ReadTimeout("read timed out"))

    with patch("microsoft_ad.asset_connectors.user_assets_sync.wait_exponential", return_value=wait_fixed(0.01)):
        action = build_action(max_duration=0.2)
        results = action.run(ARGUMENTS)

    assert results == {"fetched": 1, "pushed_batches": 0, "failed_batches": 0, "has_more": True}
    assert action.error_message is None
    assert "most_recent_datetime" not in read_context(tmp_path)
    assert any("time limit" in log["message"] for log in sent_logs(api))


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

        assert results == {
            "fetched": 3,
            "pushed_batches": 3,
            "failed_batches": 0,
            "has_more": False,
        }
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


def retryable_answer(status_code: int, retry_after: str | None = None) -> RetryableStatusError:
    response = requests.Response()
    response.status_code = status_code
    if retry_after is not None:
        response.headers["Retry-After"] = retry_after
    return RetryableStatusError(f"HTTP {status_code}", response=response)


def run_retries(connector: MicrosoftADUserAssetSyncConnector, errors: list[Exception]) -> list[float]:
    """Run `_retry` over attempts raising `errors` then succeeding, and return the waits asked."""
    waits: list[float] = []

    def record_wait(timeout: float) -> bool:
        waits.append(timeout)
        return False

    connector._stop_event.wait = record_wait  # type: ignore[method-assign,assignment]
    attempts = iter(errors)
    for attempt in connector._retry():
        with attempt:
            if error := next(attempts, None):
                raise error
    return waits


@pytest.mark.parametrize(
    "error, expected_wait",
    [
        (retryable_answer(429, retry_after="7"), 7),
        (retryable_answer(503, retry_after="2"), 2),
        # No or invalid `Retry-After`: the exponential backoff
        (retryable_answer(429), 1),
        (retryable_answer(429, retry_after="soon"), 1),
        (requests.ConnectionError("connection reset"), 1),
    ],
)
def test_retry_waits_for_the_retry_after_of_the_answer(tmp_path, error, expected_wait):
    connector = MicrosoftADUserAssetSyncConnector(module=MicrosoftADModule(), data_path=tmp_path)

    assert run_retries(connector, [error]) == [expected_wait]


def test_retry_gives_up_when_the_retry_after_exceeds_the_time_left(tmp_path):
    connector = MicrosoftADUserAssetSyncConnector(module=MicrosoftADModule(), data_path=tmp_path)
    error = retryable_answer(429, retry_after=str(connector.PUSH_RETRY_MAX_DELAY + 1))

    with pytest.raises(RetryableStatusError):
        run_retries(connector, [error])


def test_retry_wakes_up_when_the_connector_is_stopped(tmp_path):
    connector = MicrosoftADUserAssetSyncConnector(module=MicrosoftADModule(), data_path=tmp_path)
    Timer(0.1, connector.stop).start()
    started = time.monotonic()

    with pytest.raises(RetryableStatusError):
        for attempt in connector._retry():
            with attempt:
                raise retryable_answer(429, retry_after="60")

    # Stopped after 0.1 s: well before the 60 s asked, and before the 1 s of the shortest backoff
    assert time.monotonic() - started < 0.8


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
    # Optional on both sides: the action fails with a clear error when it is empty
    assert "basedn" not in connector["arguments"]["required"]
    assert "basedn" not in action["arguments"]["required"]
    assert "failed_batches" in action["results"]["properties"]
    assert action["arguments"]["properties"]["batch_size"]["default"] == 1000


BASEDN_ERROR = "A base DN is required to synchronize Active Directory users"


@pytest.mark.parametrize("basedn", [None, ""])
def test_run_fails_at_once_without_a_base_dn(build_action, api, tmp_path, basedn):
    arguments = {**ARGUMENTS, "basedn": basedn}
    action = build_action()

    with patch.object(MicrosoftADUserAssetSyncConnector, "asset_fetch_cycle") as asset_fetch_cycle:
        results = action.run(arguments)

    assert results == {"fetched": 0, "pushed_batches": 0, "failed_batches": 0, "has_more": False}
    assert action.error_message == BASEDN_ERROR
    asset_fetch_cycle.assert_not_called()
    assert not requests_to(api, PUSH_URL)
    assert any(log["level"] == "error" and log["message"] == BASEDN_ERROR for log in sent_logs(api))
    assert "most_recent_datetime" not in read_context(tmp_path)


def test_run_pushes_ad_users_to_the_asset_connector(tmp_path, api):
    entries = [build_entry("S-1-5-21-1", datetime(2024, 6, 1))]

    with fake_directory(entries):
        results = build_real_action(tmp_path).run({**ARGUMENTS, "batch_size": 1000})

    assert results == {"fetched": 1, "pushed_batches": 1, "failed_batches": 0, "has_more": False}
    assert pushed_sids(api) == ["S-1-5-21-1"]
    assert requests_to(api, LOGS_URL)
    assert read_context(tmp_path)["most_recent_datetime"] == "20240601000000.0Z"


def test_run_logs_the_users_that_could_not_be_mapped(tmp_path, api):
    entries = [
        build_entry("S-1-5-21-1", datetime(2024, 1, 1)),
        build_entry("S-1-5-21-2", datetime(2025, 6, 1)),
        build_entry("S-1-5-21-3", datetime(2023, 3, 1)),
    ]
    original_map = MicrosoftADUserAssetConnector.map_user_fields

    def map_or_fail(connector, entry):
        if entry["attributes"]["objectSid"] == "S-1-5-21-2":
            raise ValueError("unexpected attribute")
        return original_map(connector, entry)

    with (
        fake_directory(entries),
        patch.object(MicrosoftADUserAssetConnector, "map_user_fields", map_or_fail),
    ):
        results = build_real_action(tmp_path).run(ARGUMENTS)

    assert results == {"fetched": 2, "pushed_batches": 2, "failed_batches": 0, "has_more": False}
    assert sorted(pushed_sids(api)) == ["S-1-5-21-1", "S-1-5-21-3"]
    logs = sent_logs(api)
    assert any(log["level"] == "error" and "Failed to map user" in log["message"] for log in logs)
    assert any(
        log["level"] == "warning"
        and "1 user(s) could not be mapped" in log["message"]
        and "full resync" in log["message"]
        for log in logs
    )
    # Known limit: the cursor moves past the skipped user, only a full resync reads it again
    assert read_context(tmp_path)["most_recent_datetime"] == "20250601000000.0Z"


@pytest.mark.parametrize(
    "sorts, first_run_sids, first_run_checkpoint",
    [
        # Sorted: the checkpoint is committed after each pushed batch (one entry behind)
        (True, ["S-1-5-21-3", "S-1-5-21-1"], "20230301000000.0Z"),
        # Sort refused, directory order: only committed at the end of a complete cycle
        (False, ["S-1-5-21-1", "S-1-5-21-2"], None),
    ],
)
def test_interrupted_cycle_resumes_without_missing_users(tmp_path, api, sorts, first_run_sids, first_run_checkpoint):
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
        fake_directory(entries, sorts=sorts),
        patch.object(MicrosoftADUserAssetSyncConnector, "post_assets_to_api", post_then_stop),
    ):
        first = build_real_action(tmp_path).run(ARGUMENTS)
        # Without the sort, the next run is the next scheduled one, not an immediate re-run
        assert first["has_more"] is sorts
        assert pushed_sids(api) == first_run_sids
        assert read_context(tmp_path).get("most_recent_datetime") == first_run_checkpoint

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
        fake_directory(entries, sorts=False),
        patch.object(MicrosoftADUserAssetSyncConnector, "post_assets_to_api", post_and_record_checkpoint),
    ):
        results = build_real_action(tmp_path).run(ARGUMENTS)

    assert results == {"fetched": 2, "pushed_batches": 2, "failed_batches": 0, "has_more": False}
    assert pushed_sids(api) == ["S-1-5-21-2", "S-1-5-21-5"]
    # Sort refused: the checkpoint is not committed after each batch, only once the whole directory has been read
    assert checkpoints_at_push == ["20240201000000.0Z", "20240201000000.0Z"]
    context = read_context(tmp_path)
    assert context["most_recent_datetime"] == "20250601000000.0Z"
    assert context["seen_sids_at_checkpoint"] == ["S-1-5-21-2"]


def test_sorted_cycle_commits_the_checkpoint_after_each_batch(tmp_path, api):
    entries = [
        build_entry("S-1-5-21-1", datetime(2024, 1, 1)),
        build_entry("S-1-5-21-2", datetime(2025, 6, 1)),
        build_entry("S-1-5-21-3", datetime(2023, 3, 1)),
    ]
    original_post = MicrosoftADUserAssetSyncConnector.post_assets_to_api
    checkpoints_after_push: list[str | None] = []

    def post_and_record_checkpoint(connector, assets, url):
        response = original_post(connector, assets, url)
        checkpoints_after_push.append(connector.most_recent_datetime)
        return response

    with (
        fake_directory(entries),
        patch.object(MicrosoftADUserAssetSyncConnector, "post_assets_to_api", post_and_record_checkpoint),
    ):
        results = build_real_action(tmp_path).run(ARGUMENTS)

    assert results["has_more"] is False
    assert pushed_sids(api) == ["S-1-5-21-3", "S-1-5-21-1", "S-1-5-21-2"]
    # One entry behind the pushed batch: the cursor moves once the next entry is read
    assert checkpoints_after_push == [None, "20230301000000.0Z", "20240101000000.0Z"]
    assert read_context(tmp_path)["most_recent_datetime"] == "20250601000000.0Z"


def test_run_warns_when_the_directory_refuses_to_sort(tmp_path, api):
    entries = [build_entry("S-1-5-21-1", datetime(2024, 1, 1))]

    with fake_directory(entries, sorts=False):
        results = build_real_action(tmp_path).run(ARGUMENTS)

    assert results == {"fetched": 1, "pushed_batches": 1, "failed_batches": 0, "has_more": False}
    assert any(
        log["level"] == "warning" and "refused to sort the users by creation date" in log["message"]
        for log in sent_logs(api)
    )
    assert read_context(tmp_path)["most_recent_datetime"] == "20240101000000.0Z"


@pytest.mark.parametrize(
    "sorts, checkpoint_after_error",
    [
        # Sorted: the checkpoint stays on the pushed batches (one entry behind)
        (True, "20230301000000.0Z"),
        # Sort refused: the checkpoint must not jump to the most recent user read, past the unread pages
        (False, None),
    ],
)
def test_run_fails_when_the_search_ends_on_an_error_page(tmp_path, api, sorts, checkpoint_after_error):
    entries = [
        build_entry("S-1-5-21-1", datetime(2024, 1, 1)),
        build_entry("S-1-5-21-2", datetime(2025, 6, 1)),
        build_entry("S-1-5-21-3", datetime(2023, 3, 1)),
        build_entry("S-1-5-21-4", datetime(2024, 2, 1)),
    ]

    with fake_directory(entries, sorts=sorts, error_after=2, page_size=2):
        with pytest.raises(AssetConnectorSearchError, match="busy"):
            build_real_action(tmp_path).run(ARGUMENTS)

    assert read_context(tmp_path).get("most_recent_datetime") == checkpoint_after_error
    assert any(log["level"] == "error" and "stopped before its last page" in log["message"] for log in sent_logs(api))

    # The next run reads the users of the unread pages
    with fake_directory(entries, sorts=sorts):
        build_real_action(tmp_path).run(ARGUMENTS)

    assert set(pushed_sids(api)) == {"S-1-5-21-1", "S-1-5-21-2", "S-1-5-21-3", "S-1-5-21-4"}
    assert read_context(tmp_path)["most_recent_datetime"] == "20250601000000.0Z"


def test_paged_search_passes_the_sort_control_and_follows_the_cookie(tmp_path):
    entries = [build_entry(f"S-1-5-21-{i}", datetime(2024, 1, i)) for i in range(1, 6)]
    directory = FakeDirectory(entries, page_size=2)
    connector = MicrosoftADUserAssetSyncConnector(module=MicrosoftADModule(), data_path=tmp_path)
    connector._ldap_client = directory
    connector.configuration = {  # type: ignore[assignment]
        "basedn": "DC=example,DC=com",
        "sekoia_base_url": BASE_URL,
        "sekoia_api_key": "api-key",
    }

    read = [entry["attributes"]["objectSid"] for entry in connector._run_paged_search()]

    # Each page in server order: the whole stream is sorted by `whenCreated`
    assert read == [f"S-1-5-21-{i}" for i in range(1, 6)]
    assert connector.sorted_search is True
    assert [search["controls"] for search in directory.searches] == [[sort_control("whenCreated")]] * 3
    assert [search["paged_cookie"] for search in directory.searches] == [None, b"2", b"4"]


def test_sorted_checkpoint_never_skips_users_of_a_page_not_fully_pushed(tmp_path, api):
    # ldap3's paged search yields each page in reverse: a batch ending inside a page
    # committed the newest user of that page, ahead of its older users not pushed yet
    entries = [build_entry(f"S-1-5-21-{i}", datetime(2024, 1, i)) for i in range(1, 9)]
    original_post = MicrosoftADUserAssetSyncConnector.post_assets_to_api
    pushes_before_stop = {"left": 1}

    def post_then_stop(connector, assets, url):
        response = original_post(connector, assets, url)
        pushes_before_stop["left"] -= 1
        if pushes_before_stop["left"] == 0:
            connector.stop()
        return response

    # Pages of 4 users, batches of 3: the first batch ends inside the first page
    with (
        fake_directory(entries, page_size=4),
        patch.object(MicrosoftADUserAssetSyncConnector, "post_assets_to_api", post_then_stop),
    ):
        first = build_real_action(tmp_path).run({**ARGUMENTS, "batch_size": 3})
        assert first["has_more"] is True
        pushed_first = set(pushed_sids(api))
        checkpoint = read_context(tmp_path)["most_recent_datetime"]
        not_pushed = [entry for entry in entries if entry["attributes"]["objectSid"] not in pushed_first]
        assert all(
            entry["attributes"]["whenCreated"].strftime("%Y%m%d%H%M%S.0Z") >= checkpoint for entry in not_pushed
        )

        build_real_action(tmp_path).run({**ARGUMENTS, "batch_size": 3})

    assert set(pushed_sids(api)) == {entry["attributes"]["objectSid"] for entry in entries}
