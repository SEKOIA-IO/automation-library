import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, PropertyMock, create_autospec, patch

import pytest
import requests_mock
from polyswarm_api import exceptions as ps_exceptions
from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE
from tenacity import Retrying, stop_after_attempt

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.client import DEFAULT_TIMEOUT, RETRY_TOTAL
from polyswarm_modules.coerce import as_text
from polyswarm_modules.connector_polyswarm_intel_feed import (
    MAX_BACKOFF_SECONDS,
    MAX_LIST_ITEMS,
    MAX_WINDOW_MINUTES,
    PUSH_RETRY_CEILING_SECONDS,
    IntelFeed,
    IntelFeedConfiguration,
    escape_lucene_phrase,
    escape_lucene_term,
    event_characters,
    format_window_bound,
    polyscore_band,
)
from tests.helpers import autospec_request

API_KEY = "test-api-key"


def make_connector(data_storage: str, module: PolyswarmModule, **overrides: Any) -> IntelFeed:
    """Build a connector with every outbound surface replaced by a mock."""
    connector = IntelFeed(module=module, data_path=Path(data_storage))
    connector.configuration = {
        "intake_key": "test-intake-key",
        "intake_server": "https://intake.example",
        "frequency": 900,
        "min_polyscore": 0.7,
        "lookback_minutes": 60,
        "lag_seconds": 0,
        "max_events_per_run": 100,
        **overrides,
    }
    connector.log = create_autospec(connector.log)
    connector.log_exception = create_autospec(connector.log_exception)
    # Like the SDK, answer with one event id per event the intake accepted.
    connector.push_events_to_intakes = create_autospec(
        connector.push_events_to_intakes, side_effect=lambda events: [f"id-{n}" for n in range(len(events))]
    )
    connector.sleep = create_autospec(connector.sleep)
    return connector


@pytest.fixture
def connector(data_storage: str, module: PolyswarmModule) -> IntelFeed:
    return make_connector(data_storage, module)


def make_artifact(
    sha256: str,
    created: datetime,
    *,
    polyscore: float = 0.9,
    family: str = "Emotet",
    tags: list[str] | None = None,
    malicious: int = 12,
    benign: int = 3,
    total: int = 15,
) -> SimpleNamespace:
    """A stand in for a polyswarm_api Metadata resource."""
    document: dict[str, Any] = {
        "artifact": {"sha256": sha256, "created": created.isoformat()},
        "scan": {
            "latest_scan": {"polyscore": polyscore},
            "detections": {"malicious": malicious, "benign": benign, "total": total},
        },
        "polyunite": {"malware_family": family},
        "tags": tags if tags is not None else ["ransomware"],
        "community": "default",
    }
    return SimpleNamespace(
        json=document,
        sha256=sha256,
        sha1="",
        md5="",
        created=created,
        polyscore=polyscore,
        malicious=malicious,
        benign=benign,
        total_detections=total,
        first_seen=created,
        last_scanned=created,
        mimetype="application/x-dosexec",
        extended_mimetype="PE32 executable",
        filenames=["invoice.exe"],
    )


def install_api(mock_api_class: MagicMock, search: Any) -> MagicMock:
    api = mock_api_class.return_value
    # A side effect rather than a replacement, so the call is still checked against
    # the real method's signature before the fake runs.
    api.search_by_metadata.side_effect = search
    return api


def pushed_events(connector: IntelFeed) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for call in connector.push_events_to_intakes.call_args_list:
        events.extend(call.args[0])
    return events


def logged_messages(connector: IntelFeed) -> list[str]:
    return [str(call.kwargs.get("message", "")) for call in connector.log.call_args_list]


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------


def test_every_operator_filter_lands_in_the_server_side_query(data_storage: str, module: PolyswarmModule) -> None:
    connector = make_connector(
        data_storage,
        module,
        families=["emotet", "redline"],
        tags=["sector:healthcare"],
        min_polyscore=0.85,
    )
    start = datetime(2026, 9, 20, 10, 0, 0, tzinfo=UTC)
    query = connector.build_query(start, start + timedelta(hours=1))

    assert "artifact.created:[2026-09-20T10:00:00 TO 2026-09-20T11:00:00]" in query
    assert "scan.latest_scan.polyscore:>=0.85" in query
    assert "polyunite.malware_family:emotet" in query
    assert "cape_sandbox_v2.malware_family:redline" in query
    assert "scan.*.*.metadata.malware_family:*emotet*" in query
    assert 'tags:"sector:healthcare"' in query


def test_no_family_and_no_tag_falls_back_to_the_curated_feed(connector: IntelFeed) -> None:
    start = datetime(2026, 9, 20, 10, 0, 0, tzinfo=UTC)
    assert 'tags:"feed:premium"' in connector.build_query(start, start + timedelta(minutes=5))


def test_only_three_selectors_of_each_kind_are_used(data_storage: str, module: PolyswarmModule) -> None:
    connector = make_connector(
        data_storage,
        module,
        families=["a", "b", "c", "d"],
        tags=["t1", "t2", "t3", "t4"],
    )
    start = datetime(2026, 9, 20, 10, 0, 0, tzinfo=UTC)
    query = connector.build_query(start, start + timedelta(minutes=5))

    assert "polyunite.malware_family:d" not in query
    assert 'tags:"t4"' not in query


def test_lucene_metacharacters_cannot_break_out_of_a_term() -> None:
    assert escape_lucene_term("red line") == "redline"
    assert escape_lucene_term("a:b OR *") == "a\\:bOR\\*"
    assert escape_lucene_phrase('say "hi"') == 'say \\"hi\\"'


def test_polyscore_bands_are_not_engine_verdicts() -> None:
    assert polyscore_band(None) == "unknown"
    assert polyscore_band(0.1) == "benign"
    assert polyscore_band(0.5) == "suspicious"
    assert polyscore_band(0.95) == "malicious"


# ---------------------------------------------------------------------------
# First run, with no checkpoint
# ---------------------------------------------------------------------------


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_first_run_with_no_checkpoint_pulls_the_lookback_window(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    created = datetime.now(UTC) - timedelta(minutes=10)
    seen_queries: list[str] = []

    def search(query: str) -> Iterator[Any]:
        seen_queries.append(query)
        yield make_artifact("aa" * 32, created)

    install_api(mock_api_class, search)

    assert connector.next_run() == 1

    # Built through the shared factory, which is where the retrying adapter
    # and the default timeout are actually configured from.
    mock_api_class.assert_called_once_with(key=API_KEY, community="default", timeout=DEFAULT_TIMEOUT)

    # No checkpoint existed, so the window opened lookback_minutes ago.
    lower = re.search(r"artifact\.created:\[(\S+) TO (\S+)\]", seen_queries[0])
    assert lower is not None
    window_start = datetime.strptime(lower.group(1), "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)
    expected = datetime.now(UTC) - timedelta(minutes=60)
    assert abs((window_start - expected).total_seconds()) < 30

    events = pushed_events(connector)
    assert len(events) == 1
    assert events[0]["sha256"] == "aa" * 32
    assert events[0]["polyscore_band"] == "malicious"
    assert events[0]["families"] == ["Emotet"]
    assert events[0]["tags"] == ["ransomware"]
    assert events[0]["permalink"].endswith("aa" * 32)

    # The checkpoint now holds the end of the window that was covered.
    assert connector.checkpoint.offset > window_start


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_the_api_key_reaches_no_event_and_no_log_line(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    def search(query: str) -> Iterator[Any]:
        yield make_artifact("bb" * 32, datetime.now(UTC) - timedelta(minutes=5))

    install_api(mock_api_class, search)
    connector.next_run()

    assert all(API_KEY not in str(event) for event in pushed_events(connector))
    assert all(API_KEY not in message for message in logged_messages(connector))


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_an_artifact_with_no_readable_digest_is_dropped(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)
    broken = make_artifact("", created)

    def search(query: str) -> Iterator[Any]:
        yield broken
        yield make_artifact("cc" * 32, created)

    install_api(mock_api_class, search)

    assert connector.next_run() == 1
    assert pushed_events(connector)[0]["sha256"] == "cc" * 32


# ---------------------------------------------------------------------------
# Second run, resuming from the checkpoint
# ---------------------------------------------------------------------------


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_second_run_resumes_from_the_checkpoint_and_does_not_re_emit(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)
    boundary = make_artifact("dd" * 32, created)
    seen_queries: list[str] = []

    def search(query: str) -> Iterator[Any]:
        seen_queries.append(query)
        # A Lucene range is inclusive at both ends, so the platform hands the
        # boundary artifact back on the next window as well.
        yield boundary

    install_api(mock_api_class, search)

    assert connector.next_run() == 1
    first_checkpoint = connector.checkpoint.offset

    assert connector.next_run() == 0
    assert connector.push_events_to_intakes.call_count == 1

    # The second window opened where the first one closed, and the checkpoint
    # still moved forward even though the window held nothing new.
    second_start = re.search(r"artifact\.created:\[(\S+) TO", seen_queries[1])
    assert second_start is not None
    assert second_start.group(1) == first_checkpoint.strftime("%Y-%m-%dT%H:%M:%S")
    assert connector.checkpoint.offset >= first_checkpoint


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_restart_reads_the_checkpoint_back_off_disk(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)
    artifact = make_artifact("ee" * 32, created)

    def search(query: str) -> Iterator[Any]:
        yield artifact

    install_api(mock_api_class, search)

    first = make_connector(data_storage, module)
    assert first.next_run() == 1
    position = first.checkpoint.offset

    # A fresh process, same data path. It must neither restart from the
    # lookback window nor repeat the artifact it already forwarded.
    second = make_connector(data_storage, module)
    assert second.checkpoint.offset == position
    assert second.next_run() == 0
    second.push_events_to_intakes.assert_not_called()


# ---------------------------------------------------------------------------
# Paging
# ---------------------------------------------------------------------------


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_results_are_collected_across_more_than_one_page(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)
    page_one = [make_artifact(f"{index:02x}" * 32, created) for index in range(1, 4)]
    page_two = [make_artifact(f"{index:02x}" * 32, created) for index in range(4, 6)]
    served: list[int] = []

    def search(query: str) -> Iterator[Any]:
        # The client hands back a generator that fetches the next page only when
        # the current one runs out, so a page is served on demand.
        for page in (page_one, page_two):
            served.append(len(page))
            yield from page

    install_api(mock_api_class, search)

    assert connector.next_run() == 5
    assert served == [3, 2]
    assert len(pushed_events(connector)) == 5


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_an_overfull_minimum_window_is_pushed_whole_so_the_feed_cannot_stall(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module, max_events_per_run=2)
    created = datetime.now(UTC) - timedelta(minutes=5)
    artifacts = [make_artifact(f"{index:02x}" * 32, created) for index in range(1, 6)]
    spans: list[float] = []

    def search(query: str) -> Iterator[Any]:
        found = re.search(r"artifact\.created:\[(\S+) TO (\S+)\]", query)
        assert found is not None
        start, end = (datetime.strptime(group, "%Y-%m-%dT%H:%M:%S") for group in found.groups())
        spans.append((end - start).total_seconds())
        yield from artifacts

    install_api(mock_api_class, search)

    before = connector.checkpoint.offset
    assert connector.next_run() == 5

    # The window was halved down to the floor, and only there was the ceiling waived.
    assert spans[-1] <= 60
    assert len(spans) > 1
    assert len(pushed_events(connector)) == 5
    assert connector.checkpoint.offset > before
    assert any("pushed whole" in message for message in logged_messages(connector))


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_window_already_at_the_minimum_is_pushed_whole_on_the_first_try(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module, max_events_per_run=1, lookback_minutes=1, lag_seconds=5)
    created = datetime.now(UTC) - timedelta(seconds=30)
    calls: list[str] = []

    def search(query: str) -> Iterator[Any]:
        calls.append(query)
        yield from [make_artifact(f"{index:02x}" * 32, created) for index in range(1, 4)]

    install_api(mock_api_class, search)

    assert connector.next_run() == 3
    assert len(calls) == 1


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_an_overfull_window_is_narrowed_until_it_fits(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    """A busy period must not stall the feed: ask for less time instead of giving up."""
    connector = make_connector(data_storage, module, max_events_per_run=2)
    created = datetime.now(UTC) - timedelta(minutes=5)
    attempts: list[int] = []

    def search(query: str) -> Iterator[Any]:
        attempts.append(len(attempts))
        if len(attempts) == 1:
            yield from [make_artifact(f"{index:02x}" * 32, created) for index in range(1, 5)]
        else:
            yield make_artifact("ff" * 32, created)

    install_api(mock_api_class, search)

    before = connector.checkpoint.offset
    pushed = connector.next_run()

    assert pushed == 1
    assert len(attempts) == 2
    connector.push_events_to_intakes.assert_called_once()
    # The checkpoint moved forward, but only over the window actually covered.
    assert connector.checkpoint.offset > before
    assert any("narrowing it to" in message for message in logged_messages(connector))


# ---------------------------------------------------------------------------
# Filtering
# ---------------------------------------------------------------------------


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_the_polyscore_filter_excludes_a_result(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    """The filter is a query term, so the exclusion happens where the query runs."""
    connector = make_connector(data_storage, module, min_polyscore=0.8, families=["emotet"])
    created = datetime.now(UTC) - timedelta(minutes=5)
    corpus = [
        make_artifact("11" * 32, created, polyscore=0.95, family="Emotet"),
        make_artifact("22" * 32, created, polyscore=0.42, family="Emotet"),
        make_artifact("33" * 32, created, polyscore=0.90, family="RedLine"),
    ]

    def search(query: str) -> Iterator[Any]:
        floor = float(re.search(r"scan\.latest_scan\.polyscore:>=([\d.]+)", query).group(1))
        family = re.search(r"polyunite\.malware_family:(\w+)", query).group(1)
        for item in corpus:
            if item.polyscore >= floor and item.json["polyunite"]["malware_family"].lower() == family:
                yield item

    install_api(mock_api_class, search)

    assert connector.next_run() == 1
    digests = [event["sha256"] for event in pushed_events(connector)]
    assert digests == ["11" * 32]


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_repeated_digest_inside_one_run_is_emitted_once(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)

    def search(query: str) -> Iterator[Any]:
        yield make_artifact("44" * 32, created)
        yield make_artifact("44" * 32, created)

    install_api(mock_api_class, search)

    assert connector.next_run() == 1


# ---------------------------------------------------------------------------
# Failure paths
# ---------------------------------------------------------------------------


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_an_api_error_leaves_the_checkpoint_untouched_and_backs_off(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    def search(query: str) -> Iterator[Any]:
        raise ps_exceptions.RequestException(autospec_request(), "the request failed")
        yield  # pragma: no cover

    install_api(mock_api_class, search)

    before = connector.checkpoint.offset
    assert connector.next_run() == 0

    connector.push_events_to_intakes.assert_not_called()
    assert connector.checkpoint.offset == before

    messages = logged_messages(connector)
    assert any("RequestException" in message and "the request failed" in message for message in messages)
    assert all(API_KEY not in message for message in messages)

    connector.sleep.assert_called_once_with(float(connector.frequency))


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_repeated_failures_back_off_further_and_recover(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)
    attempts = {"count": 0}

    def search(query: str) -> Iterator[Any]:
        attempts["count"] += 1
        if attempts["count"] <= 3:
            raise ps_exceptions.UsageLimitsExceededException(autospec_request(), "429")
        yield make_artifact("55" * 32, created)

    install_api(mock_api_class, search)

    before = connector.checkpoint.offset
    for _ in range(3):
        connector.next_run()

    assert connector.checkpoint.offset == before
    delays = [call.args[0] for call in connector.sleep.call_args_list]
    assert delays == [900.0, 1800.0, 3600.0]

    assert connector.next_run() == 1
    assert connector.checkpoint.offset > before
    assert connector.backoff_seconds() == 900.0


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_an_empty_window_is_not_an_error(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    """The client raises on a 204 rather than returning an empty list."""

    def search(query: str) -> Iterator[Any]:
        raise ps_exceptions.NoResultsException(autospec_request(), "204")
        yield  # pragma: no cover

    install_api(mock_api_class, search)

    before = connector.checkpoint.offset
    assert connector.next_run() == 0
    connector.push_events_to_intakes.assert_not_called()
    # An empty window was still covered, so the checkpoint moves past it.
    assert connector.checkpoint.offset > before


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_window_that_has_not_opened_yet_makes_no_request(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    """With the whole lookback held back by the lag, there is nothing to ask for."""
    connector = make_connector(data_storage, module, lookback_minutes=1, lag_seconds=3600)
    install_api(mock_api_class, lambda query: iter(()))

    assert connector.next_run() == 0
    mock_api_class.assert_not_called()


# ---------------------------------------------------------------------------
# Restart safety
# ---------------------------------------------------------------------------


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_push_that_returns_fewer_ids_than_events_holds_the_window_and_retries_it(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    """The SDK never raises from a push: a failed chunk is logged and missing from the returned ids.

    The connector has to notice the shortfall itself. Moving the checkpoint
    anyway is the bug that silently skips a window for good.
    """
    connector = make_connector(data_storage, module)
    created = datetime.now(UTC) - timedelta(minutes=5)
    artifacts = [make_artifact(f"{index:02x}" * 32, created) for index in range(1, 4)]

    def search(query: str) -> Iterator[Any]:
        yield from artifacts

    install_api(mock_api_class, search)
    connector.push_events_to_intakes.side_effect = lambda events: ["id-0"]

    before_checkpoint = connector.checkpoint.offset
    before_digests = connector.remembered_digests()

    assert connector.next_run() == 0

    assert connector.checkpoint.offset == before_checkpoint
    assert connector.remembered_digests() == before_digests
    assert any("accepted 1 of 3 events" in message for message in logged_messages(connector))
    connector.sleep.assert_called_once_with(float(connector.frequency))
    assert connector.backoff_seconds() == 900.0

    # Retried on the next cycle rather than lost: the same artifacts go out again.
    connector.push_events_to_intakes.side_effect = lambda events: [f"id-{n}" for n in range(len(events))]
    connector.push_events_to_intakes.reset_mock()

    assert connector.next_run() == 3
    assert len(pushed_events(connector)) == 3
    assert connector.checkpoint.offset > before_checkpoint
    assert connector.remembered_digests() == {"01" * 32, "02" * 32, "03" * 32}


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_push_that_accepts_nothing_is_a_failure_too(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module)
    created = datetime.now(UTC) - timedelta(minutes=5)

    def search(query: str) -> Iterator[Any]:
        yield make_artifact("66" * 32, created)

    install_api(mock_api_class, search)
    connector.push_events_to_intakes.side_effect = lambda events: []

    before = connector.checkpoint.offset
    assert connector.next_run() == 0
    assert connector.checkpoint.offset == before


# ---------------------------------------------------------------------------
# Catch up pacing
# ---------------------------------------------------------------------------


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_catch_up_does_not_sleep_between_empty_windows_until_the_frontier_is_reached(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    """A long backlog is walked at the speed of the API, not one slice per frequency."""
    # 1000 minutes behind, six hour slices: 360, 360, then the last 280 reach the frontier.
    connector = make_connector(data_storage, module, lookback_minutes=1000, lag_seconds=300)

    def search(query: str) -> Iterator[Any]:
        raise ps_exceptions.NoResultsException(autospec_request(), "204")
        yield  # pragma: no cover

    install_api(mock_api_class, search)

    for _ in range(3):
        assert connector.next_run() == 0

    delays = [call.args[0] for call in connector.sleep.call_args_list]
    assert delays == [0, 0, connector.frequency]
    expected = datetime.now(UTC) - timedelta(seconds=300)
    assert abs((connector.checkpoint.offset - expected).total_seconds()) < 30


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_run_that_pushed_events_still_waits_once_it_has_caught_up(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)

    def search(query: str) -> Iterator[Any]:
        yield make_artifact("77" * 32, created)

    install_api(mock_api_class, search)

    assert connector.next_run() == 1
    connector.sleep.assert_called_once_with(connector.frequency)


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_run_that_pushed_events_does_not_wait_while_still_behind(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module, lookback_minutes=1000)
    created = datetime.now(UTC) - timedelta(minutes=900)

    def search(query: str) -> Iterator[Any]:
        yield make_artifact("78" * 32, created)

    install_api(mock_api_class, search)

    assert connector.next_run() == 1
    connector.sleep.assert_called_once_with(0)


# ---------------------------------------------------------------------------
# Metrics, client reuse, liveness
# ---------------------------------------------------------------------------


@patch("polyswarm_modules.connector_polyswarm_intel_feed.EVENTS_LAG", autospec=True)
@patch("polyswarm_modules.connector_polyswarm_intel_feed.FORWARD_EVENTS_DURATION", autospec=True)
@patch("polyswarm_modules.connector_polyswarm_intel_feed.OUTCOMING_EVENTS", autospec=True)
@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_metrics_are_labelled_by_intake_key(
    mock_api_class: MagicMock,
    outcoming: MagicMock,
    duration: MagicMock,
    lag: MagicMock,
    connector: IntelFeed,
) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)

    def search(query: str) -> Iterator[Any]:
        yield from [make_artifact(f"{index:02x}" * 32, created) for index in range(1, 3)]

    install_api(mock_api_class, search)
    connector.next_run()

    outcoming.labels.assert_called_once_with(intake_key="test-intake-key")
    outcoming.labels.return_value.inc.assert_called_once_with(2)
    duration.labels.assert_called_once_with(intake_key="test-intake-key")
    duration.labels.return_value.observe.assert_called_once()
    lag.labels.assert_called_once_with(intake_key="test-intake-key")
    assert lag.labels.return_value.set.call_args.args[0] >= 0


@patch("polyswarm_modules.connector_polyswarm_intel_feed.OUTCOMING_EVENTS", autospec=True)
@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_failed_push_counts_no_forwarded_events(
    mock_api_class: MagicMock, outcoming: MagicMock, connector: IntelFeed
) -> None:
    def search(query: str) -> Iterator[Any]:
        yield make_artifact("79" * 32, datetime.now(UTC) - timedelta(minutes=5))

    install_api(mock_api_class, search)
    connector.push_events_to_intakes.side_effect = lambda events: []
    connector.next_run()

    outcoming.labels.assert_not_called()


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_one_client_serves_every_run(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    def search(query: str) -> Iterator[Any]:
        raise ps_exceptions.NoResultsException(autospec_request(), "204")
        yield  # pragma: no cover

    install_api(mock_api_class, search)
    connector.next_run()
    connector.next_run()

    mock_api_class.assert_called_once()


def test_the_liveness_check_does_not_flag_a_quiet_narrow_feed() -> None:
    assert IntelFeed.seconds_without_events == 0


def test_the_descriptor_states_the_late_qualifying_limitation() -> None:
    description = json.loads(Path("connector_intel_feed.json").read_text())["description"]
    assert "never pulled" in description
    assert "rescan" in description


def test_sleep_uses_the_stop_event_not_a_bare_sleep(data_storage: str, module: PolyswarmModule) -> None:
    """Non negotiable: a stop or restart request must be honoured immediately.

    A bare time.sleep would make the connector wait out the whole pause
    before it noticed a stop, and Sekoia may restart an idle connector on its
    own to keep it from freezing.
    """
    connector = IntelFeed(module=module, data_path=Path(data_storage))
    connector.configuration = {"intake_key": "test-intake-key"}
    connector._stop_event = create_autospec(Event, instance=True)

    connector.sleep(5)

    connector._stop_event.wait.assert_called_once_with(5)


def test_sleep_does_nothing_for_a_non_positive_duration(data_storage: str, module: PolyswarmModule) -> None:
    connector = IntelFeed(module=module, data_path=Path(data_storage))
    connector.configuration = {"intake_key": "test-intake-key"}
    connector._stop_event = create_autospec(Event, instance=True)

    connector.sleep(0)

    connector._stop_event.wait.assert_not_called()


# ---------------------------------------------------------------------------
# Timezones
# ---------------------------------------------------------------------------


def test_a_naive_datetime_is_treated_as_utc_not_local_time() -> None:
    """A PolySwarm API result can hand back a naive datetime for a field the platform reports in UTC.

    Reading it as the machine's local zone instead would silently shift it,
    which is the recurring bug this guards against.
    """
    naive = datetime(2026, 9, 20, 10, 0, 0)
    assert as_text(naive) == "2026-09-20T10:00:00+00:00"


def test_an_aware_datetime_in_another_zone_is_normalised_to_utc() -> None:
    eastern = timezone(timedelta(hours=-4))
    aware = datetime(2026, 9, 20, 6, 0, 0, tzinfo=eastern)
    assert as_text(aware) == "2026-09-20T10:00:00+00:00"


def test_format_window_bound_normalises_a_non_utc_aware_datetime() -> None:
    eastern = timezone(timedelta(hours=-4))
    aware = datetime(2026, 9, 20, 6, 0, 0, tzinfo=eastern)
    assert format_window_bound(aware) == "2026-09-20T10:00:00"


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_naive_created_timestamp_from_the_api_is_not_shifted_by_local_time(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    """End to end: a naive created timestamp on a pushed event stays exactly as PolySwarm reported it."""
    naive_created = datetime(2026, 9, 20, 10, 0, 0)
    artifact = make_artifact("77" * 32, naive_created)

    def search(query: str) -> Iterator[Any]:
        yield artifact

    install_api(mock_api_class, search)

    assert connector.next_run() == 1
    event = pushed_events(connector)[0]
    assert event["timestamp"] == "2026-09-20T10:00:00+00:00"


# ---------------------------------------------------------------------------
# Shared client
# ---------------------------------------------------------------------------


def test_the_client_has_retries_installed_for_safe_methods(data_storage: str, module: PolyswarmModule) -> None:
    """Adopting build_client is only meaningful if the retrying adapter is actually mounted."""
    connector = IntelFeed(module=module, data_path=Path(data_storage))
    connector.configuration = {"intake_key": "test-intake-key"}

    api = connector.client()

    for scheme in ("http://", "https://"):
        adapter = api.session.get_adapter(scheme)
        assert adapter.max_retries.total == RETRY_TOTAL


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_the_client_uses_the_connector_level_community_override(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module, community="isac-sharing")

    connector.client()

    mock_api_class.assert_called_once_with(key=API_KEY, community="isac-sharing", timeout=DEFAULT_TIMEOUT)


# ---------------------------------------------------------------------------
# Descriptor completeness
# ---------------------------------------------------------------------------


def test_the_descriptor_matches_the_model() -> None:
    """A descriptor promising a value the model refuses is a silent rejection for the customer.

    Only the fields this connector itself declares are checked. intake_server
    and intake_key come from the SDK's own DefaultConnectorConfiguration,
    whose Python default is not what the descriptor shows: the descriptor's
    default there is a UI suggestion, the same convention every connector in
    the public library uses for those two fields.
    """
    descriptor = json.loads(Path("connector_intel_feed.json").read_text())
    properties = descriptor["arguments"]["properties"]
    fields = IntelFeedConfiguration.model_fields
    own_fields = set(IntelFeedConfiguration.__annotations__)

    for name, declared in properties.items():
        if name not in own_fields:
            continue
        field = fields[name]
        if "default" in declared:
            # families and tags default through default_factory rather than a
            # plain default, so the actual default has to be resolved the same
            # way pydantic resolves it rather than compared to the raw field.
            assert declared["default"] == field.get_default(call_default_factory=True), f"{name} default differs"
        bounds = {type(m).__name__: getattr(m, "ge", getattr(m, "le", None)) for m in field.metadata}
        if "maximum" in declared and "Le" in bounds:
            assert declared["maximum"] == bounds["Le"], f"{name} maximum differs"
        if "minimum" in declared and "Ge" in bounds:
            assert declared["minimum"] == bounds["Ge"], f"{name} minimum differs"


def test_liveness_rests_on_the_heartbeat_not_on_events(connector: IntelFeed) -> None:
    """A narrow feed can legitimately match nothing for days.

    The inherited six hour event based check would call that connector dead and
    have the platform restart it in a loop, so it is off, and the heartbeat
    answers instead. The threshold has to clear a cycle that slept its whole
    frequency and then backed off, or a connector waiting on an outage would be
    restarted for waiting.
    """
    assert connector.seconds_without_events == 0
    assert connector.last_heartbeat_threshold >= 3 * connector.frequency
    assert connector.last_heartbeat_threshold > MAX_BACKOFF_SECONDS
    # The SDK keeps retrying one push for an hour, and a failed push then backs off.
    assert connector.last_heartbeat_threshold >= PUSH_RETRY_CEILING_SECONDS + MAX_BACKOFF_SECONDS
    assert PUSH_RETRY_CEILING_SECONDS > 3600


def test_the_heartbeat_threshold_is_off_before_the_configuration_is_attached() -> None:
    """is_alive can be asked before the connector is configured."""
    bare = IntelFeed.__new__(IntelFeed)

    assert bare.last_heartbeat_threshold == 0


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_feed_that_matches_nothing_says_so_with_its_filters(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    """A correct but empty feed must not be silent.

    A filter narrow enough to match nothing for days is the normal case for this
    connector, and silence reads to an operator exactly like a broken one. The
    line has to name the filters, because the filters are almost always the
    reason and the only thing the operator can change.
    """
    connector.configuration.families = ["emotet"]
    connector.configuration.tags = ["banker"]
    install_api(mock_api_class, lambda query: iter([]))

    connector.next_run()

    said = [m for m in logged_messages(connector) if "matched" in m]

    assert said, f"the connector logged nothing about an empty window: {logged_messages(connector)}"
    assert "emotet" in said[0]
    assert "banker" in said[0]
    assert str(connector.configuration.min_polyscore) in said[0]


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_catching_up_does_not_log_a_line_for_every_empty_slice(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    """Only once the connector has reached the frontier, or a backlog floods the log."""
    connector.configuration.lookback_minutes = 1000
    install_api(mock_api_class, lambda query: iter([]))

    connector.next_run()

    assert not [m for m in logged_messages(connector) if "matched" in m]


# ---------------------------------------------------------------------------
# Oversized events, through the real SDK push
# ---------------------------------------------------------------------------


def real_push(connector: IntelFeed) -> None:
    """Put the SDK's own push_events_to_intakes back, instead of the mock make_connector installs."""
    del connector.push_events_to_intakes


def intake_answering_per_event(mocker: requests_mock.Mocker) -> Any:
    """An intake that answers like the real one: one event id per event in the batch."""

    def answer(request: Any, context: Any) -> dict[str, list[str]]:
        context.status_code = 200
        return {"event_ids": [f"id-{n}" for n in range(len(request.json()["jsons"]))]}

    return mocker.post("https://intake.example/batch", json=answer)


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_an_oversized_event_is_dropped_and_does_not_stall_the_feed(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    """The SDK discards an event over 250000 characters and returns no id for it.

    Counted as a failed push, that holds the checkpoint and rebuilds the same
    window forever. This goes through the real SDK push so the discard is real.
    """
    connector = make_connector(data_storage, module)
    real_push(connector)
    created = datetime.now(UTC) - timedelta(minutes=5)
    normal = make_artifact("aa" * 32, created)
    huge = make_artifact("bb" * 32, created)
    # A field the connector does not cap, so the event is over the limit however the lists are bounded.
    huge.mimetype = "x" * (EVENT_BYTES_MAX_SIZE + 10)

    install_api(mock_api_class, lambda query: iter([normal, huge]))
    before = connector.checkpoint.offset

    with requests_mock.Mocker() as mocker:
        intake = intake_answering_per_event(mocker)
        assert connector.next_run() == 1

    sent = [json.loads(body) for call in intake.request_history for body in call.json()["jsons"]]
    assert [event["sha256"] for event in sent] == ["aa" * 32]
    assert connector.checkpoint.offset > before
    assert connector.remembered_digests() == {"aa" * 32}
    assert any("longer than" in message for message in logged_messages(connector))
    assert connector._consecutive_failures == 0


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_window_holding_only_an_oversized_event_still_moves_on(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module)
    real_push(connector)
    huge = make_artifact("cc" * 32, datetime.now(UTC) - timedelta(minutes=5))
    huge.mimetype = "x" * (EVENT_BYTES_MAX_SIZE + 10)
    install_api(mock_api_class, lambda query: iter([huge]))
    before = connector.checkpoint.offset

    with requests_mock.Mocker() as mocker:
        intake = intake_answering_per_event(mocker)
        assert connector.next_run() == 0

    assert intake.call_count == 0
    assert connector.checkpoint.offset > before
    assert not [m for m in logged_messages(connector) if "matched" in m]


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_an_artifact_with_thousands_of_filenames_fits_the_intake_limit(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module)
    real_push(connector)
    artifact = make_artifact("dd" * 32, datetime.now(UTC) - timedelta(minutes=5))
    artifact.filenames = [f"payload-{n}-" + "y" * 600 + ".exe" for n in range(20000)]
    artifact.json["tags"] = [f"tag-{n}" for n in range(20000)]
    artifact.json["families"] = [f"family-{n}" for n in range(20000)]
    install_api(mock_api_class, lambda query: iter([artifact]))

    with requests_mock.Mocker() as mocker:
        intake = intake_answering_per_event(mocker)
        assert connector.next_run() == 1

    (body,) = [body for call in intake.request_history for body in call.json()["jsons"]]
    event = json.loads(body)
    assert len(event["filenames"]) == MAX_LIST_ITEMS
    assert len(event["tags"]) == MAX_LIST_ITEMS
    assert len(event["families"]) == MAX_LIST_ITEMS
    assert max(len(name) for name in event["filenames"]) <= 512
    assert event_characters(event) < EVENT_BYTES_MAX_SIZE


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_real_push_that_fails_still_holds_the_window(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    """The shortfall check still works against the real SDK when the intake refuses the batch."""
    connector = make_connector(data_storage, module)
    real_push(connector)
    # One attempt only, so the test does not wait out the SDK's hour of retries.
    connector._retry = lambda: Retrying(stop=stop_after_attempt(1), reraise=True)  # type: ignore[method-assign]
    install_api(
        mock_api_class, lambda query: iter([make_artifact("ee" * 32, datetime.now(UTC) - timedelta(minutes=5))])
    )
    before = connector.checkpoint.offset

    with requests_mock.Mocker() as mocker:
        mocker.post("https://intake.example/batch", status_code=500)
        assert connector.next_run() == 0

    assert connector.checkpoint.offset == before
    assert any("accepted 0 of 1 events" in message for message in logged_messages(connector))


# ---------------------------------------------------------------------------
# One unreadable artifact must not stall the feed
# ---------------------------------------------------------------------------


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
@pytest.mark.parametrize("field", ["scan", "polyunite", "artifact"])
def test_an_artifact_with_a_malformed_field_is_counted_unreadable_and_the_rest_flow(
    mock_api_class: MagicMock, connector: IntelFeed, field: str
) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)
    broken = make_artifact("f1" * 32, created)
    broken.json[field] = "not an object"
    broken.sha256 = ""
    good = make_artifact("f2" * 32, created)
    install_api(mock_api_class, lambda query: iter([broken, good]))
    before = connector.checkpoint.offset

    assert connector.next_run() == 1

    assert [event["sha256"] for event in pushed_events(connector)] == ["f2" * 32]
    assert connector.checkpoint.offset > before
    assert any("could not be read" in message for message in logged_messages(connector))


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_an_artifact_that_raises_during_conversion_does_not_fail_the_cycle(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)
    broken = make_artifact("f3" * 32, created)
    broken.json["scan"] = ["a", "list"]
    broken.created = 10**400  # an int too large for any conversion that follows
    install_api(mock_api_class, lambda query: iter([broken, make_artifact("f4" * 32, created)]))

    assert connector.next_run() == 1
    assert connector._consecutive_failures == 0


# ---------------------------------------------------------------------------
# Catch up remembers the span that fit
# ---------------------------------------------------------------------------


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_the_span_that_fit_is_remembered_and_the_next_run_starts_from_it(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module, lookback_minutes=1000, max_events_per_run=2)
    spans: list[float] = []

    def search(query: str) -> Iterator[Any]:
        bounds = re.search(r"artifact\.created:\[(\S+) TO (\S+)\]", query)
        start = datetime.fromisoformat(bounds.group(1))
        end = datetime.fromisoformat(bounds.group(2))
        span = (end - start).total_seconds()
        spans.append(span)
        # Busy: more than the ceiling in anything wider than 100 minutes.
        count = 5 if span > 6000 else 1
        for n in range(count):
            yield make_artifact(f"{n + 1:02x}" * 32, start + timedelta(seconds=n + 1))

    install_api(mock_api_class, search)

    connector.next_run()
    first_run_attempts = len(spans)
    assert first_run_attempts > 1
    fitted = spans[-1]
    assert connector.window_span_seconds() == fitted

    # A new instance on the same data path: the span survives a restart.
    again = make_connector(data_storage, module, lookback_minutes=1000, max_events_per_run=2)
    assert again.window_span_seconds() == fitted

    spans.clear()
    connector.next_run()
    assert spans[0] == fitted, "the next run starts from the span that fit, not from the ceiling"
    # It fit, so the span doubles for the run after.
    assert connector.window_span_seconds() == min(2 * fitted, MAX_WINDOW_MINUTES * 60)


def test_the_span_starts_at_the_ceiling_and_ignores_a_corrupt_value(
    data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module)
    assert connector.window_span_seconds() == MAX_WINDOW_MINUTES * 60
    with connector.digests as cache:
        cache["window_seconds"] = "soon"
    assert connector.window_span_seconds() == MAX_WINDOW_MINUTES * 60
    with connector.digests as cache:
        cache["window_seconds"] = 5
    assert connector.window_span_seconds() == 60


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def test_a_checkpoint_older_than_the_lookback_ceiling_is_logged(data_storage: str, module: PolyswarmModule) -> None:
    connector = make_connector(data_storage, module)
    stale = datetime.now(UTC) - timedelta(days=45)
    (Path(data_storage) / "context.json").write_text(json.dumps({"most_recent_date_seen": stale.isoformat()}))

    connector.checkpoint

    said = [m for m in logged_messages(connector) if "lookback ceiling" in m]
    assert said and "not pulled" in said[0]


def test_a_recent_checkpoint_logs_nothing_about_clamping(data_storage: str, module: PolyswarmModule) -> None:
    connector = make_connector(data_storage, module)
    recent = datetime.now(UTC) - timedelta(hours=2)
    (Path(data_storage) / "context.json").write_text(json.dumps({"most_recent_date_seen": recent.isoformat()}))

    connector.checkpoint

    assert not [m for m in logged_messages(connector) if "lookback ceiling" in m]


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_the_idle_line_is_said_once_and_again_after_events_arrive(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    created = datetime.now(UTC) - timedelta(minutes=1)
    answers: list[list[Any]] = [[], [], [], [make_artifact("a1" * 32, created)], [], []]
    install_api(mock_api_class, lambda query: iter(answers.pop(0)))

    def idle_lines() -> int:
        return len([m for m in logged_messages(connector) if "matched" in m])

    connector.next_run()
    connector.next_run()
    connector.next_run()
    assert idle_lines() == 1

    connector.next_run()
    connector.next_run()
    connector.next_run()
    assert idle_lines() == 2


# ---------------------------------------------------------------------------
# Truncated windows, drop counters, redaction, digest ordering
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing",
    [ps_exceptions.NoResultsException, ps_exceptions.NotFoundException],
)
@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_later_page_with_no_result_fails_the_cycle_and_holds_the_checkpoint(
    mock_api_class: MagicMock, missing: type[Exception], connector: IntelFeed
) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)

    def search(query: str) -> Iterator[Any]:
        yield make_artifact("a1" * 32, created)
        yield make_artifact("a2" * 32, created)
        raise missing(autospec_request(), "later page")

    install_api(mock_api_class, search)

    before = connector.checkpoint.offset
    assert connector.next_run() == 0

    connector.push_events_to_intakes.assert_not_called()
    assert connector.checkpoint.offset == before
    assert connector.remembered_digests() == set()
    assert connector._consecutive_failures == 1
    assert any("cut short" in message for message in logged_messages(connector))
    connector.sleep.assert_called_once_with(float(connector.frequency))


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_truncated_window_is_retried_whole_and_then_completes(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)
    attempts = {"count": 0}

    def search(query: str) -> Iterator[Any]:
        attempts["count"] += 1
        yield make_artifact("b1" * 32, created)
        if attempts["count"] == 1:
            raise ps_exceptions.NotFoundException(autospec_request(), "404")
        yield make_artifact("b2" * 32, created)

    install_api(mock_api_class, search)

    before = connector.checkpoint.offset
    assert connector.next_run() == 0
    assert connector.next_run() == 2
    assert connector.checkpoint.offset > before
    assert len(pushed_events(connector)) == 2


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_first_page_with_no_result_is_still_a_clean_empty_window(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    def search(query: str) -> Iterator[Any]:
        raise ps_exceptions.NotFoundException(autospec_request(), "404")
        yield  # pragma: no cover

    install_api(mock_api_class, search)

    before = connector.checkpoint.offset
    assert connector.next_run() == 0
    assert connector.checkpoint.offset > before
    assert connector._consecutive_failures == 0
    assert not any("cut short" in message for message in logged_messages(connector))


@patch("polyswarm_modules.connector_polyswarm_intel_feed.COLLECTED_EVENTS", autospec=True)
@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_collected_events_counts_each_drop_reason(
    mock_api_class: MagicMock, collected: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module)
    created = datetime.now(UTC) - timedelta(minutes=5)
    huge = make_artifact("c3" * 32, created)
    huge.filenames = ["x" * MAX_LIST_ITEMS] * MAX_LIST_ITEMS
    bad = make_artifact("", created)

    def search(query: str) -> Iterator[Any]:
        yield make_artifact("c1" * 32, created)
        yield make_artifact("c1" * 32, created)
        yield make_artifact("c1" * 32, created)
        yield bad
        yield huge

    install_api(mock_api_class, search)
    with patch(
        "polyswarm_modules.connector_polyswarm_intel_feed.event_characters",
        side_effect=lambda event: EVENT_BYTES_MAX_SIZE + 1 if event["sha256"] == "c3" * 32 else 10,
    ):
        assert connector.next_run() == 1

    counts = {
        call.kwargs["reason"]: collected.labels.return_value.inc.call_args_list[index].args[0]
        for index, call in enumerate(collected.labels.call_args_list)
    }
    assert counts == {"duplicate": 2, "unreadable": 1, "oversized": 1}
    assert all(call.kwargs["intake_key"] == "test-intake-key" for call in collected.labels.call_args_list)


@patch("polyswarm_modules.connector_polyswarm_intel_feed.COLLECTED_EVENTS", autospec=True)
@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_a_halved_window_counts_drops_only_once(
    mock_api_class: MagicMock, collected: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module, max_events_per_run=1)
    created = datetime.now(UTC) - timedelta(minutes=5)
    calls = {"count": 0}

    def search(query: str) -> Iterator[Any]:
        calls["count"] += 1
        yield make_artifact("d1" * 32, created)
        yield make_artifact("d1" * 32, created)
        if calls["count"] == 1:
            yield make_artifact("d2" * 32, created)

    install_api(mock_api_class, search)
    connector.next_run()

    assert calls["count"] == 2
    incs = [args.args[0] for args in collected.labels.return_value.inc.call_args_list]
    assert incs == [1]


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_an_unexpected_error_is_logged_with_its_message_but_never_the_key(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    def search(query: str) -> Iterator[Any]:
        raise KeyError(f"missing field near {connector.module.configuration.apikey}")
        yield  # pragma: no cover

    install_api(mock_api_class, search)
    connector.next_run()

    messages = logged_messages(connector)
    assert any("KeyError" in message and "missing field near [REDACTED]" in message for message in messages)
    assert all(connector.module.configuration.apikey not in message for message in messages)


@patch("polyswarm_modules.client.PolyswarmAPI", autospec=True)
def test_digests_are_saved_before_the_checkpoint_moves(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)

    def search(query: str) -> Iterator[Any]:
        yield make_artifact("e1" * 32, created)

    install_api(mock_api_class, search)
    before = connector.checkpoint.offset

    class FailingCheckpoint:
        @property
        def offset(self) -> datetime:
            return before

        @offset.setter
        def offset(self, value: datetime) -> None:
            raise RuntimeError("crash at checkpoint write")

    with patch.object(IntelFeed, "checkpoint", new_callable=PropertyMock, return_value=FailingCheckpoint()):
        with pytest.raises(RuntimeError):
            connector.next_run()

    assert "e1" * 32 in connector.remembered_digests()
    assert connector.checkpoint.offset == before


def test_remembered_digests_survive_a_retry_that_has_none_of_its_own(connector: IntelFeed) -> None:
    connector.remember_digests(["f1" * 32])
    connector.remember_digests([])
    assert connector.remembered_digests() == {"f1" * 32}
