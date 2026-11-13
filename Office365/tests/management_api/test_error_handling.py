import pytest

from office365.management_api.error_handling import FailureTracker, extract_error_metadata


class TestFailureTracker:
    def test_record_increments_for_same_signature(self):
        tracker = FailureTracker()
        assert tracker.record("a") == 1
        assert tracker.record("a") == 2
        assert tracker.record("a") == 3

    def test_record_resets_on_signature_change(self):
        tracker = FailureTracker()
        tracker.record("a")
        tracker.record("a")
        assert tracker.record("b") == 1
        assert tracker.last_signature == "b"

    def test_reset_returns_previous_count_and_clears_state(self):
        tracker = FailureTracker()
        tracker.record("a")
        tracker.record("a")
        previous = tracker.reset()
        assert previous == 2
        assert tracker.consecutive == 0
        assert tracker.last_signature is None
        assert tracker.first_failure_time is None

    def test_reset_returns_zero_when_no_failures(self):
        tracker = FailureTracker()
        assert tracker.reset() == 0

    @pytest.mark.parametrize(
        "count,expected",
        [
            (1, True),
            (2, True),
            (3, True),
            (4, False),
            (5, False),
            (9, False),
            (10, True),
            (15, False),
            (20, True),
            (50, True),
            (99, False),
            (100, True),
            (150, False),
            (200, True),
            (250, False),
            (300, True),
        ],
    )
    def test_should_log_dedup_pattern(self, count, expected):
        tracker = FailureTracker()
        for _ in range(count):
            tracker.record("a")
        assert tracker.should_log() is expected

    @pytest.mark.parametrize(
        "count,expected_level",
        [
            (1, "warning"),
            (5, "warning"),
            (6, "error"),
            (50, "error"),
            (51, "critical"),
            (1000, "critical"),
        ],
    )
    def test_log_level_escalates_with_streak(self, count, expected_level):
        tracker = FailureTracker()
        for _ in range(count):
            tracker.record("a")
        assert tracker.log_level == expected_level

    def test_duration_seconds_is_zero_when_no_failures(self):
        tracker = FailureTracker()
        assert tracker.duration_seconds == 0.0

    def test_duration_seconds_is_positive_after_record(self):
        tracker = FailureTracker()
        tracker.record("a")
        assert tracker.duration_seconds >= 0.0


class TestExtractErrorMetadata:
    def test_extracts_error_code_and_message_from_json(self):
        body = '{"error": {"code": "AF20023", "message": "Throttled"}}'
        meta = extract_error_metadata(body, status_code=429)
        assert meta["status_code"] == 429
        assert meta["error_code"] == "AF20023"
        assert meta["error_message"] == "Throttled"
        assert "body" not in meta

    def test_truncates_long_message(self):
        long_msg = "x" * 500
        body = f'{{"error": {{"code": "X", "message": "{long_msg}"}}}}'
        meta = extract_error_metadata(body, status_code=500)
        assert meta["error_message"].endswith("...(truncated)")
        assert len(meta["error_message"]) < len(long_msg)

    def test_falls_back_to_truncated_body_for_html(self):
        html = "<html>" + ("a" * 5000) + "</html>"
        meta = extract_error_metadata(html, status_code=504)
        assert meta["status_code"] == 504
        assert meta["body"].endswith("...(truncated)")
        assert len(meta["body"]) <= 250  # truncated body + suffix
        assert "error_code" not in meta
        assert "error_message" not in meta

    def test_handles_empty_body(self):
        meta = extract_error_metadata("", status_code=500)
        assert meta["status_code"] == 500
        assert meta["body"] == ""

    def test_handles_invalid_json(self):
        meta = extract_error_metadata("not json {", status_code=500)
        assert meta["status_code"] == 500
        assert meta["body"] == "not json {"

    def test_no_status_code_field_when_omitted(self):
        meta = extract_error_metadata("anything", status_code=None)
        assert "status_code" not in meta

    def test_json_without_error_key_falls_back_to_body(self):
        body = '{"data": "ok"}'
        meta = extract_error_metadata(body, status_code=500)
        assert meta["body"] == body

    def test_short_body_is_not_truncated(self):
        body = "short"
        meta = extract_error_metadata(body, status_code=500)
        assert meta["body"] == "short"
        assert not meta["body"].endswith("...(truncated)")
