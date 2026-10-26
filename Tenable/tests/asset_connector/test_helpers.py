import os
import time

from tenable_conn.asset_connector.helpers import (
    FindingKey,
    TraversalState,
    advance_checkpoint,
    asset_details_to_export,
    boundary_from_json,
    boundary_to_json,
    dedup_key,
    effective_timestamp,
    DESCRIPTION_MAX_LENGTH,
    REFERENCE_MAX_LENGTH,
    REFERENCES_MAX_COUNT,
    TRUNCATION_SUFFIX,
    limit_description,
    limit_references,
    parse_datetime_to_timestamp,
    truncate_description,
)
from tenable_conn.asset_connector.models.asset_details_model import AssetDetails

from tests.asset_connector.factories import T1, T2, T3


def test_truncate_description_multi_sentence():
    desc = "This is the first sentence. This is the second sentence. And a third."
    result = truncate_description(desc)
    assert result == "This is the first sentence. See more details on Tenable"


def test_truncate_description_single_sentence():
    desc = "Only one sentence here."
    result = truncate_description(desc)
    assert result == "Only one sentence here. See more details on Tenable"


def test_truncate_description_exclamation():
    desc = "Watch out! This is dangerous."
    result = truncate_description(desc)
    assert result == "Watch out! See more details on Tenable"


def test_truncate_description_question_mark():
    desc = "Is this a vulnerability? Yes it is."
    result = truncate_description(desc)
    assert result == "Is this a vulnerability? See more details on Tenable"


def test_truncate_description_no_punctuation():
    desc = "A description with no sentence-ending punctuation"
    result = truncate_description(desc)
    assert result == "A description with no sentence-ending punctuation See more details on Tenable"


def test_truncate_description_empty():
    assert truncate_description("") == "See more details on Tenable"


def test_truncate_description_none():
    assert truncate_description(None) == "See more details on Tenable"


def test_parse_datetime_to_timestamp_valid():
    result = parse_datetime_to_timestamp("2025-08-26T14:34:38.571Z")
    assert isinstance(result, int)
    assert result > 0


def test_parse_datetime_to_timestamp_none():
    result = parse_datetime_to_timestamp(None)
    assert result is None


def test_parse_datetime_to_timestamp_invalid():
    result = parse_datetime_to_timestamp("not-a-date")
    assert result is None


def test_details_conversion_preserves_name():
    """The details->export adapter keeps the human-readable name from Get Asset Details."""
    details = AssetDetails.model_validate({"id": "asset-x", "name": "example-asset"})
    exported = asset_details_to_export(details)
    assert exported.name == "example-asset"
    # The name is not injected into the hostnames
    assert exported.network.hostnames == []


def test_effective_timestamp_is_max_of_last_found_and_last_fixed():
    vuln = {"last_found": "2025-01-01T00:00:00Z", "last_fixed": "2025-01-02T00:00:00Z"}
    assert effective_timestamp(vuln) == 1735776000


def test_effective_timestamp_with_a_single_date():
    assert effective_timestamp({"last_found": "2025-01-01T00:00:00Z"}) == 1735689600
    assert effective_timestamp({"last_fixed": "2025-01-02T00:00:00Z"}) == 1735776000


def test_effective_timestamp_missing_or_invalid():
    assert effective_timestamp({}) is None
    assert effective_timestamp({"last_found": None, "last_fixed": None}) is None
    assert effective_timestamp({"last_found": "invalid"}) is None
    assert effective_timestamp({"last_found": "invalid", "last_fixed": "2025-01-02T00:00:00Z"}) == 1735776000


def _key(finding_id: str) -> FindingKey:
    return FindingKey(finding_id=finding_id, state="OPEN", last_found=None, last_fixed=None)


def test_dedup_key():
    vuln = {"finding_id": "f-1", "state": "OPEN", "last_found": "2025-01-01T00:00:00Z"}
    key = dedup_key(vuln)
    assert key == FindingKey(finding_id="f-1", state="OPEN", last_found="2025-01-01T00:00:00Z", last_fixed=None)
    assert key is not None and key.finding_id == "f-1" and key.state == "OPEN"
    assert dedup_key(dict(vuln)) == key
    assert dedup_key({**vuln, "state": "FIXED"}) != key
    assert dedup_key({**vuln, "last_found": "2025-01-02T00:00:00Z"}) != key
    assert dedup_key({**vuln, "last_fixed": "2025-01-02T00:00:00Z"}) != key
    assert dedup_key({"state": "OPEN"}) is None


def test_boundary_json_round_trip():
    boundary = {
        FindingKey(
            finding_id="f-2", state="FIXED", last_found="2025-01-01T00:00:00Z", last_fixed="2025-01-02T00:00:00Z"
        ),
        FindingKey(finding_id="f-1", state="OPEN", last_found="2025-01-02T00:00:00Z", last_fixed=None),
    }
    stored = boundary_to_json(boundary)
    assert stored == [
        {"finding_id": "f-1", "state": "OPEN", "last_found": "2025-01-02T00:00:00Z", "last_fixed": None},
        {
            "finding_id": "f-2",
            "state": "FIXED",
            "last_found": "2025-01-01T00:00:00Z",
            "last_fixed": "2025-01-02T00:00:00Z",
        },
    ]
    assert boundary_from_json(stored) == boundary


def test_boundary_from_json_ignores_invalid_entries():
    assert boundary_from_json(None) == set()
    assert boundary_from_json(["f-1|OPEN||", {"state": "OPEN"}, 42]) == set()
    assert boundary_from_json([{"finding_id": "f-1"}]) == {
        FindingKey(finding_id="f-1", state=None, last_found=None, last_fixed=None)
    }


def test_advance_checkpoint_unordered_findings():
    # Committed checkpoint T2/{B}, findings received out of order
    boundary = {_key("B")}
    cursor = advance_checkpoint(T2, boundary, T3, _key("C"))
    assert (cursor, boundary) == (T3, {_key("C")})  # later finding: replaces the boundary
    cursor = advance_checkpoint(cursor, boundary, T2, _key("B"))
    assert (cursor, boundary) == (T3, {_key("C")})  # earlier finding: no change
    cursor = advance_checkpoint(cursor, boundary, T3, _key("D"))
    assert (cursor, boundary) == (T3, {_key("C"), _key("D")})  # same second: added to the boundary


def test_advance_checkpoint_edge_cases():
    boundary: set[FindingKey] = set()
    # Initial sync: the first finding sets the cursor
    assert advance_checkpoint(None, boundary, T1, _key("A")) == T1
    assert boundary == {_key("A")}
    # No timestamp: ignored
    assert advance_checkpoint(T1, boundary, None, _key("X")) == T1
    assert boundary == {_key("A")}
    # Failed finding (no key): moves the cursor but stays out of the boundary
    assert advance_checkpoint(T1, boundary, T2, None) == T2
    assert boundary == set()
    assert advance_checkpoint(T2, boundary, T2, None) == T2
    assert boundary == set()


def test_naive_datetime_is_read_as_utc():
    original = os.environ.get("TZ")
    os.environ["TZ"] = "Europe/Paris"
    time.tzset()
    try:
        assert parse_datetime_to_timestamp("2025-01-01T00:00:00") == 1735689600
        assert effective_timestamp({"last_found": "2025-01-01T00:00:00"}) == 1735689600
    finally:
        if original is None:
            os.environ.pop("TZ", None)
        else:
            os.environ["TZ"] = original
        time.tzset()


def test_limit_description():
    assert limit_description("short") == "short"
    exact = "a" * DESCRIPTION_MAX_LENGTH
    assert limit_description(exact) == exact

    limited = limit_description("a" * (DESCRIPTION_MAX_LENGTH + 1))
    assert len(limited) == DESCRIPTION_MAX_LENGTH
    assert limited.endswith(TRUNCATION_SUFFIX)


def test_limit_references():
    assert limit_references(None) == []
    references = [f"https://example.com/{i}" for i in range(REFERENCES_MAX_COUNT + 5)]
    assert limit_references(references) == references[:REFERENCES_MAX_COUNT]
    long_reference = "https://example.com/" + "a" * REFERENCE_MAX_LENGTH
    # An over-long URL is dropped, not cut: the next valid ones are kept
    assert limit_references([long_reference, "https://example.com/ok"]) == ["https://example.com/ok"]


def _state(committed_cursor=T2, boundary=(), export_start=T3) -> TraversalState:
    return TraversalState(committed_cursor, frozenset(boundary), export_start)


def test_traversal_state_already_sent():
    key = _key("a")
    state = _state(boundary={key})
    # At the committed second and in the boundary
    assert state.already_sent(T2, T2, key) is True
    # In the boundary but at another second: a new version, sent
    assert state.already_sent(T1, T1, key) is False
    # Future-dated (capped at the export start) and in the boundary
    assert state.already_sent(T3 + 100, state.cap_time(T3 + 100), key) is True
    # Not in the boundary, or without key
    assert state.already_sent(T2, T2, _key("b")) is False
    assert state.already_sent(T2, T2, None) is False


def test_traversal_state_cap_time():
    state = _state()
    assert state.cap_time(T3 + 100) == T3
    assert state.cap_time(T1) == T1
    assert state.cap_time(None) is None


def test_traversal_state_record_lookup_failure():
    state = _state()
    state.record_lookup_failure(T3)
    state.record_lookup_failure(T1)
    assert (state.retry_count, state.retry_from) == (2, T1)

    # Without time: retried from the committed cursor
    state = _state()
    state.record_lookup_failure(None)
    assert (state.retry_count, state.retry_from) == (1, T2)

    # Without time during an initial sync: nothing to cap at
    state = _state(committed_cursor=None)
    state.record_lookup_failure(None)
    assert (state.retry_count, state.retry_from) == (1, None)


def test_traversal_state_next_checkpoint_without_failure():
    state = _state()
    state.track(T3, _key("c"))
    assert state.next_checkpoint() == (T3, {_key("c")})


def test_traversal_state_next_checkpoint_failure_after_committed():
    state = _state(committed_cursor=T1)
    state.track(T3, _key("c"))
    state.record_lookup_failure(T2)
    state.track(T2, None)
    assert state.next_checkpoint() == (T2, set())


def test_traversal_state_next_checkpoint_failure_at_or_before_committed():
    state = _state(committed_cursor=T2, boundary={_key("b")})
    state.track(T3, _key("c"))
    state.record_lookup_failure(T2)
    assert state.next_checkpoint() == (T2, {_key("b")})

    state = _state(committed_cursor=T2, boundary={_key("b")})
    state.track(T3, _key("c"))
    state.record_lookup_failure(T1)
    assert state.next_checkpoint() == (T2, {_key("b")})


def test_traversal_state_next_checkpoint_empty_initial_sync():
    state = _state(committed_cursor=None)
    assert state.initial_sync is True
    assert state.next_checkpoint() == (T3, set())
