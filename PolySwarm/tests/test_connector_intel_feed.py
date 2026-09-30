import json
import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from polyswarm_api import exceptions as ps_exceptions

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.client import DEFAULT_TIMEOUT, RETRY_TOTAL
from polyswarm_modules.connector_polyswarm_intel_feed import (
    IntelFeed,
    IntelFeedConfiguration,
    _as_text,
    escape_lucene_phrase,
    escape_lucene_term,
    format_window_bound,
    polyscore_band,
)

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
    connector.log = MagicMock()
    connector.log_exception = MagicMock()
    connector.push_events_to_intakes = MagicMock(return_value=[])
    connector.sleep = MagicMock()
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
    api.search_by_metadata = search
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


@patch("polyswarm_modules.client.PolyswarmAPI")
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


@patch("polyswarm_modules.client.PolyswarmAPI")
def test_the_api_key_reaches_no_event_and_no_log_line(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    def search(query: str) -> Iterator[Any]:
        yield make_artifact("bb" * 32, datetime.now(UTC) - timedelta(minutes=5))

    install_api(mock_api_class, search)
    connector.next_run()

    assert all(API_KEY not in str(event) for event in pushed_events(connector))
    assert all(API_KEY not in message for message in logged_messages(connector))


@patch("polyswarm_modules.client.PolyswarmAPI")
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


@patch("polyswarm_modules.client.PolyswarmAPI")
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


@patch("polyswarm_modules.client.PolyswarmAPI")
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


@patch("polyswarm_modules.client.PolyswarmAPI")
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


@patch("polyswarm_modules.client.PolyswarmAPI")
def test_a_capped_run_pushes_nothing_holds_the_checkpoint_and_stops_paging(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    connector = make_connector(data_storage, module, max_events_per_run=2)
    created = datetime.now(UTC) - timedelta(minutes=5)
    page_one = [make_artifact(f"{index:02x}" * 32, created) for index in range(1, 4)]
    page_two = [make_artifact(f"{index:02x}" * 32, created) for index in range(4, 6)]
    served: list[int] = []

    def search(query: str) -> Iterator[Any]:
        for page in (page_one, page_two):
            served.append(len(page))
            yield from page

    install_api(mock_api_class, search)

    before = connector.checkpoint.offset
    assert connector.next_run() == 0

    connector.push_events_to_intakes.assert_not_called()
    assert connector.checkpoint.offset == before
    # Each attempt stops at the first page, because the generator is lazy, and
    # the window is halved and retried until it hits the floor.
    assert set(served) == {3}
    assert len(served) > 1
    assert any("Even a 60 second window" in message for message in logged_messages(connector))


@patch("polyswarm_modules.client.PolyswarmAPI")
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


@patch("polyswarm_modules.client.PolyswarmAPI")
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


@patch("polyswarm_modules.client.PolyswarmAPI")
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


@patch("polyswarm_modules.client.PolyswarmAPI")
def test_an_api_error_leaves_the_checkpoint_untouched_and_backs_off(
    mock_api_class: MagicMock, connector: IntelFeed
) -> None:
    def search(query: str) -> Iterator[Any]:
        raise ps_exceptions.RequestException(MagicMock(), "the request failed")
        yield  # pragma: no cover

    install_api(mock_api_class, search)

    before = connector.checkpoint.offset
    assert connector.next_run() == 0

    connector.push_events_to_intakes.assert_not_called()
    assert connector.checkpoint.offset == before

    messages = logged_messages(connector)
    assert any("RequestException" in message for message in messages)
    assert all("the request failed" not in message for message in messages)
    assert all(API_KEY not in message for message in messages)

    connector.sleep.assert_called_once_with(float(connector.frequency))


@patch("polyswarm_modules.client.PolyswarmAPI")
def test_repeated_failures_back_off_further_and_recover(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    created = datetime.now(UTC) - timedelta(minutes=5)
    attempts = {"count": 0}

    def search(query: str) -> Iterator[Any]:
        attempts["count"] += 1
        if attempts["count"] <= 3:
            raise ps_exceptions.UsageLimitsExceededException(MagicMock(), "429")
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


@patch("polyswarm_modules.client.PolyswarmAPI")
def test_an_empty_window_is_not_an_error(mock_api_class: MagicMock, connector: IntelFeed) -> None:
    """The client raises on a 204 rather than returning an empty list."""

    def search(query: str) -> Iterator[Any]:
        raise ps_exceptions.NoResultsException(MagicMock(), "204")
        yield  # pragma: no cover

    install_api(mock_api_class, search)

    before = connector.checkpoint.offset
    assert connector.next_run() == 0
    connector.push_events_to_intakes.assert_not_called()
    # An empty window was still covered, so the checkpoint moves past it.
    assert connector.checkpoint.offset > before


@patch("polyswarm_modules.client.PolyswarmAPI")
def test_a_window_that_has_not_opened_yet_makes_no_request(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    """With the whole lookback held back by the lag, there is nothing to ask for."""
    connector = make_connector(data_storage, module, lookback_minutes=1, lag_seconds=3600)
    install_api(mock_api_class, MagicMock())

    assert connector.next_run() == 0
    mock_api_class.assert_not_called()


# ---------------------------------------------------------------------------
# Restart safety
# ---------------------------------------------------------------------------


@patch("polyswarm_modules.client.PolyswarmAPI")
def test_a_push_failure_partway_through_a_cycle_leaves_the_checkpoint_and_digests_untouched(
    mock_api_class: MagicMock, data_storage: str, module: PolyswarmModule
) -> None:
    """The single most repeated production bug in this library: advancing position on a partial push.

    Events are collected, then pushed, then the checkpoint moves and the
    digests are remembered, in that order. If the push raises, everything
    after it must not run, so the same window is collected and pushed again
    on the next cycle instead of the artifacts being silently skipped.
    """
    connector = make_connector(data_storage, module)
    created = datetime.now(UTC) - timedelta(minutes=5)
    artifact = make_artifact("66" * 32, created)

    def search(query: str) -> Iterator[Any]:
        yield artifact

    install_api(mock_api_class, search)
    connector.push_events_to_intakes.side_effect = RuntimeError("intake unreachable")

    before_checkpoint = connector.checkpoint.offset
    before_digests = connector.remembered_digests()

    with pytest.raises(RuntimeError):
        connector.next_run()

    assert connector.checkpoint.offset == before_checkpoint
    assert connector.remembered_digests() == before_digests

    # Retried on the next cycle rather than lost: the same artifact goes out again.
    connector.push_events_to_intakes.side_effect = None
    connector.push_events_to_intakes.reset_mock()
    install_api(mock_api_class, search)

    assert connector.next_run() == 1
    connector.push_events_to_intakes.assert_called_once()
    assert connector.checkpoint.offset > before_checkpoint


def test_sleep_uses_the_stop_event_not_a_bare_sleep(data_storage: str, module: PolyswarmModule) -> None:
    """Non negotiable: a stop or restart request must be honoured immediately.

    A bare time.sleep would make the connector wait out the whole pause
    before it noticed a stop, and Sekoia may restart an idle connector on its
    own to keep it from freezing.
    """
    connector = IntelFeed(module=module, data_path=Path(data_storage))
    connector.configuration = {"intake_key": "test-intake-key"}
    connector._stop_event = MagicMock()

    connector.sleep(5)

    connector._stop_event.wait.assert_called_once_with(5)


def test_sleep_does_nothing_for_a_non_positive_duration(data_storage: str, module: PolyswarmModule) -> None:
    connector = IntelFeed(module=module, data_path=Path(data_storage))
    connector.configuration = {"intake_key": "test-intake-key"}
    connector._stop_event = MagicMock()

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
    assert _as_text(naive) == "2026-09-20T10:00:00+00:00"


def test_an_aware_datetime_in_another_zone_is_normalised_to_utc() -> None:
    eastern = timezone(timedelta(hours=-4))
    aware = datetime(2026, 9, 20, 6, 0, 0, tzinfo=eastern)
    assert _as_text(aware) == "2026-09-20T10:00:00+00:00"


def test_format_window_bound_normalises_a_non_utc_aware_datetime() -> None:
    eastern = timezone(timedelta(hours=-4))
    aware = datetime(2026, 9, 20, 6, 0, 0, tzinfo=eastern)
    assert format_window_bound(aware) == "2026-09-20T10:00:00"


@patch("polyswarm_modules.client.PolyswarmAPI")
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


@patch("polyswarm_modules.client.PolyswarmAPI")
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
