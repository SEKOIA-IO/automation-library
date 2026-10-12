import json

import pytest

from sekoiaio.operation_center import get_aggregation_query
from sekoiaio.operation_center.get_aggregation_query import GetAggregationQuery

BASE_URL = "https://app.sekoia.fake/"
API_KEY = "fake_api_key"

ARGUMENTS = {
    "aggregation_type": "count",
    "aggregation_field": "source.ip",
    "query_term": "event.dialect:windows",
    "filters": [{"field": "action.outcome", "value": "success"}],
    "earliest_time": "-1d",
    "latest_time": "now",
    "minutes_per_bucket": 60,
}


class FakeWebSocket:
    def __init__(self, response: str | Exception):
        self.response = response
        self.sent: list[str] = []
        self.closed = False

    def send(self, payload: str) -> None:
        self.sent.append(payload)

    def recv(self) -> str:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def connections(monkeypatch):
    """Replace the websocket factory and record every connection it opens."""
    opened: list[dict] = []
    responses: list[str | Exception] = []

    def fake_create_connection(url, header):
        websocket = FakeWebSocket(responses.pop(0))
        opened.append({"url": url, "header": header, "websocket": websocket})
        return websocket

    monkeypatch.setattr(get_aggregation_query, "create_connection", fake_create_connection)
    return opened, responses


def make_action() -> GetAggregationQuery:
    action = GetAggregationQuery()
    action.module.configuration = {"base_url": BASE_URL, "api_key": API_KEY}
    action.backoff = 0
    return action


def test_get_aggregation_query(connections):
    opened, responses = connections
    responses.append(json.dumps({"total": 2, "buckets": [{"key": "1.2.3.4", "count": 2}]}))

    result = make_action().run(ARGUMENTS)

    assert result == {"total": 2, "buckets": [{"key": "1.2.3.4", "count": 2}]}
    assert len(opened) == 1
    assert opened[0]["url"] == "wss://app.sekoia.fake/api/v1/events/stats"
    assert opened[0]["header"] == {"Authorization": f"Bearer {API_KEY}"}
    assert opened[0]["websocket"].closed
    assert json.loads(opened[0]["websocket"].sent[0]) == {
        "aggregation": "count",
        "field": "source.ip",
        "term": "event.dialect:windows",
        "filters": [{"field": "action.outcome", "value": "success"}],
        "range": ["-1d", "now"],
        "minutes_per_bucket": 60,
    }


def test_get_aggregation_query_default_arguments(connections):
    opened, responses = connections
    responses.append(json.dumps({"total": 0}))

    arguments = {
        "aggregation_type": "count",
        "earliest_time": "-1h",
        "latest_time": "now",
        "minutes_per_bucket": 5,
    }
    make_action().run(arguments)

    query = json.loads(opened[0]["websocket"].sent[0])
    assert query["field"] is None
    assert query["term"] == ""
    assert query["filters"] == []


def test_get_aggregation_query_retries_on_websocket_error(connections):
    opened, responses = connections
    responses.extend([ConnectionResetError("connection reset"), json.dumps({"total": 1})])

    action = make_action()
    result = action.run(ARGUMENTS)

    assert result == {"total": 1}
    assert len(opened) == 2
    assert all(connection["websocket"].closed for connection in opened)
    assert len(action._logs) == 1
    assert "WebSocket error (attempt 0): connection reset" in action._logs[0]["message"]


def test_get_aggregation_query_gives_up_after_max_attempts(connections):
    opened, responses = connections
    responses.extend([ConnectionResetError("connection reset")] * GetAggregationQuery.max_attempts)

    action = make_action()
    with pytest.raises(RuntimeError, match="WebSocket failed after 3 attempts"):
        action.run(ARGUMENTS)

    assert len(opened) == GetAggregationQuery.max_attempts
    assert all(connection["websocket"].closed for connection in opened)
    assert len(action._logs) == GetAggregationQuery.max_attempts
