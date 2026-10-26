"""
HTTP-level tests: the connector talks to a mocked Azure Resource Manager API through the real Azure SDK client
(request building, paging, deserialization and retry policy), only the AAD credential is faked.
"""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

import orjson
import pytest
import requests_mock
from azure.core.credentials import AccessToken
from azure.core.exceptions import HttpResponseError

from microsoft_sentinel import MicrosoftSentinelModule
from microsoft_sentinel.connector_microsoft_sentinel import MicrosoftSentineldConnector
from microsoft_sentinel.metrics import ENTITIES_FETCH_ERRORS

SUBSCRIPTION_ID = "4feff6df-7454-4036-923d-7b2444462416"
INCIDENTS_URL = (
    f"https://management.azure.com/subscriptions/{SUBSCRIPTION_ID}/resourceGroups/resource_group"
    "/providers/Microsoft.OperationalInsights/workspaces/workspace_name"
    "/providers/Microsoft.SecurityInsights/incidents"
)


class FakeCredential:
    """Replaces ClientSecretCredential: no call to Azure Active Directory."""

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def get_token(self, *scopes, **kwargs):
        return AccessToken("fake-token", int(time.time()) + 3600)


@pytest.fixture
def connector(symphony_storage):
    module = MicrosoftSentinelModule()
    module.configuration = {
        "tenant_id": "123456",
        "client_id": "my-id",
        "client_secret": "my-password",
        "subscription_id": SUBSCRIPTION_ID,
        "resource_group": "resource_group",
        "workspace_name": "workspace_name",
    }
    connector = MicrosoftSentineldConnector(module=module, data_path=symphony_storage)
    connector.configuration = {
        "frequency": 60,
        "chunk_size": 2,
        "intake_server": "https://intake.sekoia.io",
        "intake_key": "0123456789",
    }
    connector.push_events_to_intakes = Mock(side_effect=lambda events: [f"id-{i}" for i in range(len(events))])
    connector.log = Mock()
    connector.log_exception = Mock()

    with (
        patch("microsoft_sentinel.connector_microsoft_sentinel.ClientSecretCredential", FakeCredential),
        # keep the retries of the Azure SDK, without their backoff
        patch("azure.core.pipeline.policies.RetryPolicy.sleep"),
    ):
        yield connector


def incident_json(name: str, created: str) -> dict:
    return {
        "id": f"{INCIDENTS_URL}/{name}",
        "name": name,
        "type": "Microsoft.SecurityInsights/Incidents",
        "etag": f'"etag-{name}"',
        "properties": {
            "title": f"Incident {name}",
            "description": "Suspicious sign-in",
            "severity": "High",
            "status": "New",
            "incidentNumber": 42,
            "incidentUrl": f"https://portal.azure.com/#asset/Microsoft_Azure_Security_Insights/Incident/{name}",
            "createdTimeUtc": created,
            # modified later than created: only the creation date is tracked
            "lastModifiedTimeUtc": "2099-01-01T00:00:00.0000000Z",
            "lastActivityTimeUtc": "2021-09-01T00:00:00Z",
            "firstActivityTimeUtc": "2021-09-01T00:00:00Z",
            "labels": [{"labelName": "phishing", "labelType": "User"}],
            "owner": {"assignedTo": None, "email": None, "objectId": None, "userPrincipalName": None},
            "additionalData": {
                "alertsCount": 1,
                "bookmarksCount": 0,
                "commentsCount": 0,
                "alertProductNames": ["Azure Active Directory Identity Protection"],
                "tactics": ["InitialAccess"],
            },
            "relatedAnalyticRuleIds": [],
        },
    }


def iso(dt: datetime) -> str:
    # Azure returns 7 fractional digits (100 ns)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%f") + "7Z"


def pushed(connector) -> list[dict]:
    return [orjson.loads(e) for c in connector.push_events_to_intakes.call_args_list for e in c.kwargs["events"]]


def query(request) -> dict[str, list[str]]:
    # case-sensitive parsing (requests_mock lowercases `request.qs`)
    return parse_qs(urlparse(request.url).query)


def test_poll_through_the_azure_sdk(connector):
    t0 = (datetime.now(UTC) - timedelta(minutes=30)).replace(microsecond=123456)
    page_1 = [incident_json("A", iso(t0)), incident_json("B", iso(t0 + timedelta(seconds=1)))]
    page_2 = [incident_json("C", iso(t0 + timedelta(seconds=2)))]
    next_link = f"{INCIDENTS_URL}?api-version=2021-10-01&$skipToken=page2"
    entities = {"entities": [{"kind": "Account", "properties": {"accountName": "bob", "ntDomain": "CORP"}}]}
    errors = ENTITIES_FETCH_ERRORS.labels(intake_key="0123456789")
    errors_before = errors._value.get()
    from_date = connector.from_date

    with requests_mock.Mocker() as mock:
        mock.get(INCIDENTS_URL, json={"value": page_1, "nextLink": next_link})
        mock.get(next_link, json={"value": page_2})
        mock.post(f"{INCIDENTS_URL}/A/entities", json=entities)
        # malformed entities: DeserializationError, charged to B only
        mock.post(f"{INCIDENTS_URL}/B/entities", json={"entities": "not-a-list"})
        mock.post(f"{INCIDENTS_URL}/C/entities", json={"entities": []})

        connector.get_incidents()

        list_requests = [r for r in mock.request_history if r.method == "GET"]
        assert len(list_requests) == 2
        first = query(list_requests[0])
        expected_start = (from_date - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        assert first["$filter"] == [f"properties/createdTimeUtc ge {expected_start}"]
        assert first["$orderby"] == ["properties/createdTimeUtc asc"]
        assert query(list_requests[1])["$skipToken"] == ["page2"]
        assert list_requests[0].headers["Authorization"] == "Bearer fake-token"

    # 2 pages through nextLink, batches of chunk_size 2
    assert [len(c.kwargs["events"]) for c in connector.push_events_to_intakes.call_args_list] == [2, 1]
    events = pushed(connector)
    assert [e["name"] for e in events] == ["A", "B", "C"]
    assert events[0]["entities"] == [{"kind": "Account", "account_name": "bob", "nt_domain": "CORP"}]
    assert events[1]["entities"] == []
    assert events[0]["owner"]["assigned_to"] is None
    assert [(label["label_name"], label["label_type"]) for label in events[0]["labels"]] == [("phishing", "User")]
    assert errors._value.get() == errors_before + 1

    # 7 fractional digits are truncated to microseconds by the SDK: the checkpoint is C's date
    assert events[2]["created_time_utc"] == (t0 + timedelta(seconds=2)).isoformat()
    assert connector.cursor.offset == t0 + timedelta(seconds=2)

    # the same incidents returned again by the lookback window are not forwarded twice
    connector.push_events_to_intakes.reset_mock()
    with requests_mock.Mocker() as mock:
        mock.get(INCIDENTS_URL, json={"value": page_1 + page_2})
        connector.get_incidents()
    connector.push_events_to_intakes.assert_not_called()


def test_azure_error_while_paging_after_a_pushed_batch(connector):
    t0 = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=30)
    page_1 = [incident_json("A", iso(t0)), incident_json("B", iso(t0 + timedelta(seconds=1)))]
    page_2 = [incident_json("C", iso(t0 + timedelta(seconds=2))), incident_json("D", iso(t0 + timedelta(seconds=3)))]
    next_link = f"{INCIDENTS_URL}?api-version=2021-10-01&$skipToken=page2"
    state = {"page_2_available": False}

    def page_2_callback(request, context):
        if not state["page_2_available"]:
            context.status_code = 500
            return {"error": {"code": "InternalServerError", "message": "Something went wrong"}}
        return {"value": page_2}

    with requests_mock.Mocker() as mock:
        mock.get(INCIDENTS_URL, json={"value": page_1, "nextLink": next_link})
        mock.get(next_link, json=page_2_callback)
        mock.post(requests_mock.ANY, json={"entities": []})

        # first poll: batch [A, B] is pushed, then the second page fails after the SDK retries
        with pytest.raises(HttpResponseError):
            connector.get_incidents()
        page_2_attempts = [r for r in mock.request_history if "skipToken" in r.url]
        assert len(page_2_attempts) > 1  # retried by the Azure SDK retry policy
        assert [e["name"] for e in pushed(connector)] == ["A", "B"]
        assert connector.cursor.offset == t0 + timedelta(seconds=1)

        # the run loop keeps polling: the next poll collects the rest, without re-sending A and B
        state["page_2_available"] = True
        connector.push_events_to_intakes.reset_mock()
        waits = []

        def wait(timeout):
            waits.append(timeout)
            if len(waits) == 1:
                connector._stop_event.set()
            return True

        connector._stop_event.wait = wait
        connector.run()

    assert [e["name"] for e in pushed(connector)] == ["C", "D"]
    assert connector.cursor.offset == t0 + timedelta(seconds=3)


def test_azure_error_on_list_keeps_the_connector_running(connector):
    t0 = datetime.now(UTC).replace(microsecond=0) - timedelta(minutes=30)
    state = {"available": False}

    def list_callback(request, context):
        if not state["available"]:
            context.status_code = 503
            return {"error": {"code": "ServiceUnavailable", "message": "unavailable"}}
        return {"value": [incident_json("A", iso(t0))]}

    waits = []

    def wait(timeout):
        waits.append(timeout)
        # the API is back after the first (failed) poll, stop after the second one
        state["available"] = True
        if len(waits) == 2:
            connector._stop_event.set()
        return connector._stop_event.is_set()

    connector._stop_event.wait = wait
    with requests_mock.Mocker() as mock:
        # the SDK retries the 503, then raises HttpResponseError: the loop backs off and polls again
        mock.get(INCIDENTS_URL, json=list_callback)
        mock.post(requests_mock.ANY, json={"entities": []})
        connector.run()
        assert mock.call_count > 3

    assert connector.log_exception.call_count == 1
    assert isinstance(connector.log_exception.call_args.args[0], HttpResponseError)
    assert [e["name"] for e in pushed(connector)] == ["A"]
    assert waits == [60, 60]
