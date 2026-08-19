from datetime import UTC, datetime

import pytest

import upwind
from upwind import extract_upwind_detection_datetime


@pytest.mark.parametrize(
    ("event", "expected"),
    [
        pytest.param(
            {"first_seen_time": "2026-01-31T03:03:11Z", "last_seen_time": "2026-02-16T09:06:02Z"},
            datetime(2026, 2, 16, 9, 6, 2, tzinfo=UTC),
            id="prefers_last_seen_time",
        ),
        pytest.param(
            {"first_seen_time": "2026-03-17T11:58:50Z"},
            datetime(2026, 3, 17, 11, 58, 50, tzinfo=UTC),
            id="fallbacks_to_first_seen_time",
        ),
        pytest.param(
            {"last_seen_time": "2026-04-10T14:05:00"},
            datetime(2026, 4, 10, 14, 5, 0, tzinfo=UTC),
            id="handles_naive_timestamp",
        ),
        pytest.param(
            {"last_seen_time": "not-a-date", "first_seen_time": "2026-05-01T12:00:00Z"},
            datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC),
            id="skips_invalid_last_seen_and_uses_first_seen",
        ),
        pytest.param({"category": "no-date"}, None, id="returns_none_without_timestamps"),
    ],
)
def test_extract_detection_datetime(event: dict[str, str], expected: datetime | None) -> None:
    assert extract_upwind_detection_datetime(event) == expected


def test_extract_detection_datetime_ignores_non_datetime_parsed_values(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_isoparse(value: str) -> datetime | str:
        if value == "not-datetime":
            return "unexpected"
        return datetime(2026, 6, 1, 8, 0, 0)

    monkeypatch.setattr(upwind, "isoparse", fake_isoparse)

    event = {
        "last_seen_time": "not-datetime",
        "first_seen_time": "2026-06-01T08:00:00",
    }

    actual = extract_upwind_detection_datetime(event)

    assert actual == datetime(2026, 6, 1, 8, 0, 0, tzinfo=UTC)
