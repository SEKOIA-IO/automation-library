import io
import tempfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from beyondtrust_modules import BeyondTrustModule
from beyondtrust_modules.connector_pra_syslog import BeyondTrustPRASyslogConfiguration
from beyondtrust_modules.connector_pra_syslog import BeyondTrustPRASyslogConnector
from beyondtrust_modules.models import BeyondTrustModuleConfiguration
from beyondtrust_modules.syslog_helpers import iter_reassembled_records

SYSLOG_LINES = (
    "Mar 10 11:55:00 test BG[24183]: 1427:01:01:"
    "site=test.beyondtrustcloud.com;when=1773161700;"
    "who=JOHN DOE (john.doe@example.org);who_ip=1.2.3.4;"
    "event=setting_changed;old_api=0;new_api=1\n"
    "Mar 10 11:55:01 test BG[24182]: 1428:01:01:"
    "site=test.beyondtrustcloud.com;when=1773161701;"
    "who=JOHN DOE (john.doe@example.org);who_ip=1.2.3.4;"
    "event=setting_changed;old_api=1;new_api=0\n"
    "Mar 16 03:10:27 test BG[77159]: 1429:01:01:"
    "event=login;site=test.beyondtrustcloud.com;status=success;"
    "target=web/login;when=1773648627;"
    "who=Jane Doe (jane.doe@example.com) using oidc;who_ip=1.2.3.4\n"
)

MULTI_PART_SYSLOG_LINES = (
    "Mar 16 03:10:36 test BG[77178]: 1430:01:03:"
    "site=test.beyondtrustcloud.com;when=1773648636;\n"
    "Mar 16 03:10:36 test BG[77178]: 1430:02:03:"
    "event=user_changed;\n"
    "Mar 16 03:10:36 test BG[77178]: 1430:03:03:"
    "old_username=jane.doe@example.com\n"
)


def _make_syslog_zip(content: str) -> bytes:
    """Create an in-memory ZIP file containing a syslog file."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("syslog.log", content)
    return buf.getvalue()


@pytest.fixture
def trigger(data_storage):
    module = BeyondTrustModule()
    module.configuration = cast(
        Any,
        BeyondTrustModuleConfiguration(
            base_url="https://tenant.beyondtrustcloud.com",
            client_id="client_1",
            client_secret="SECRET",
        ).model_dump(),
    )
    trigger = BeyondTrustPRASyslogConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = cast(
        Any,
        BeyondTrustPRASyslogConfiguration(
            intake_key="intake_key",
            frequency=1800,
        ).model_dump(),
    )
    yield trigger


def _mock_oauth(mock_requests):
    mock_requests.register_uri(
        "POST",
        "https://tenant.beyondtrustcloud.com/oauth2/token",
        json={
            "access_token": "foo-token",
            "token_type": "bearer",
            "expires_in": 1799,
        },
    )


def test_fetch_events_success(trigger):
    zip_bytes = _make_syslog_zip(SYSLOG_LINES)

    with requests_mock.Mocker() as mock_requests:
        _mock_oauth(mock_requests)
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            content=zip_bytes,
            headers={"Content-Type": "application/zip"},
        )

        trigger.from_date = 0
        all_events = list(trigger.fetch_events())

        # Should yield one batch with 3 events
        assert len(all_events) == 1
        events = all_events[0]
        assert len(events) == 3
        assert "event=setting_changed" in events[0]
        assert "event=setting_changed" in events[1]
        assert "event=login" in events[2]


def test_fetch_events_with_multi_part_records(trigger):
    zip_bytes = _make_syslog_zip(MULTI_PART_SYSLOG_LINES)

    with requests_mock.Mocker() as mock_requests:
        _mock_oauth(mock_requests)
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            content=zip_bytes,
            headers={"Content-Type": "application/zip"},
        )

        trigger.from_date = 0
        all_events = list(trigger.fetch_events())

        assert len(all_events) == 1
        events = all_events[0]
        assert len(events) == 1
        # Verify multi-part reassembly
        assert events[0].startswith("site=test.beyondtrustcloud.com;when=1773648636;")
        assert "event=user_changed;" in events[0]
        assert "old_username=jane.doe@example.com" in events[0]


def test_fetch_events_updates_checkpoint(trigger):
    zip_bytes = _make_syslog_zip(SYSLOG_LINES)

    with requests_mock.Mocker() as mock_requests:
        _mock_oauth(mock_requests)
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            content=zip_bytes,
            headers={"Content-Type": "application/zip"},
        )

        trigger.from_date = 0
        list(trigger.fetch_events())

        # Most recent timestamp from the test data is 1773648627
        assert trigger.from_date == 1773648627


def test_fetch_events_filters_by_checkpoint(trigger):
    zip_bytes = _make_syslog_zip(SYSLOG_LINES)

    with requests_mock.Mocker() as mock_requests:
        _mock_oauth(mock_requests)
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            content=zip_bytes,
            headers={"Content-Type": "application/zip"},
        )

        # Set checkpoint between the first two events and the third
        trigger.from_date = 1773161701
        all_events = list(trigger.fetch_events())

        # Only the login event (when=1773648627) should pass the filter
        assert len(all_events) == 1
        assert len(all_events[0]) == 1
        assert "event=login" in all_events[0][0]


def test_fetch_events_handles_http_error(trigger):
    with requests_mock.Mocker() as mock_requests:
        _mock_oauth(mock_requests)
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            status_code=500,
            json={"error": "Internal Server Error"},
        )

        trigger.from_date = 0
        all_events = list(trigger.fetch_events())

        assert all_events == []


def test_fetch_events_handles_xml_error(trigger):
    error_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<error xmlns="http://www.beyondtrust.com/sra/namespaces/API/reporting">Invalid lsid.</error>"""

    with requests_mock.Mocker() as mock_requests:
        _mock_oauth(mock_requests)
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            content=error_xml,
            headers={"Content-Type": "text/xml; charset=UTF-8"},
        )

        trigger.from_date = 0
        all_events = list(trigger.fetch_events())

        assert all_events == []
        trigger.log.assert_any_call(
            f"An error occurred. response: {error_xml.decode('utf-8')}",
            level="error",
        )


def test_next_batch_pushes_raw_strings(trigger):
    zip_bytes = _make_syslog_zip(SYSLOG_LINES)

    with patch("beyondtrust_modules.connector_pra_syslog.time") as mock_time, requests_mock.Mocker() as mock_requests:
        _mock_oauth(mock_requests)
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            content=zip_bytes,
            headers={"Content-Type": "application/zip"},
        )

        batch_duration = 5
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.from_date = 0
        trigger.next_batch()

        # Verify push was called with raw strings, not JSON
        assert trigger.push_events_to_intakes.call_count == 1
        pushed_events = trigger.push_events_to_intakes.call_args[1]["events"]
        for event in pushed_events:
            assert isinstance(event, str)
            # Should NOT be JSON-wrapped (no leading quote or brace)
            assert not event.startswith('"')
            assert not event.startswith("{")
            assert "site=" in event or "event=" in event


def test_zip_cleanup(trigger):
    """Verify temp ZIP file is deleted after processing."""
    zip_bytes = _make_syslog_zip(SYSLOG_LINES)

    created_paths: list[Path] = []
    real_named_temp = tempfile.NamedTemporaryFile

    def tracking_named_temp(*args, **kwargs):
        f = real_named_temp(*args, **kwargs)
        created_paths.append(Path(f.name))
        return f

    with patch(
        "beyondtrust_modules.connector_pra_syslog.tempfile.NamedTemporaryFile",
        side_effect=tracking_named_temp,
    ), requests_mock.Mocker() as mock_requests:
        _mock_oauth(mock_requests)
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            content=zip_bytes,
            headers={"Content-Type": "application/zip"},
        )

        trigger.from_date = 0
        list(trigger.fetch_events())

        assert len(created_paths) == 1
        assert not created_paths[0].exists()


def test_fetch_events_handles_non_zip_content(trigger):
    """When the API returns non-ZIP content, log a warning and yield no events."""
    plain_text = b"This is not a ZIP archive"

    created_paths: list[Path] = []
    real_named_temp = tempfile.NamedTemporaryFile

    def tracking_named_temp(*args, **kwargs):
        f = real_named_temp(*args, **kwargs)
        created_paths.append(Path(f.name))
        return f

    with patch(
        "beyondtrust_modules.connector_pra_syslog.tempfile.NamedTemporaryFile",
        side_effect=tracking_named_temp,
    ), requests_mock.Mocker() as mock_requests:
        _mock_oauth(mock_requests)
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            content=plain_text,
            headers={"Content-Type": "application/zip"},
        )

        trigger.from_date = 0
        all_events = list(trigger.fetch_events())

        assert all_events == []
        trigger.log.assert_any_call(
            "Downloaded content is not a valid ZIP archive",
            level="warning",
        )

        # Verify temp file cleanup still happens
        assert len(created_paths) == 1
        assert not created_paths[0].exists()


def test_fetch_events_no_events_after_checkpoint(trigger):
    """When all events are older than checkpoint, no events should be yielded."""
    zip_bytes = _make_syslog_zip(SYSLOG_LINES)

    with requests_mock.Mocker() as mock_requests:
        _mock_oauth(mock_requests)
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            content=zip_bytes,
            headers={"Content-Type": "application/zip"},
        )

        # Set checkpoint beyond all events
        trigger.from_date = 1773648627
        all_events = list(trigger.fetch_events())

        assert all_events == []


class _FakeResponse:
    def __init__(
        self,
        *,
        ok=True,
        status_code=200,
        reason="OK",
        text="",
        headers=None,
        chunks=None,
    ):
        self.ok = ok
        self.status_code = status_code
        self.reason = reason
        self.text = text
        self.headers = headers or {}
        self._chunks = chunks or []

    def iter_content(self, chunk_size=8192):
        del chunk_size
        for chunk in self._chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk


def test_download_text_content_without_xml_error_and_iter_content_failure(trigger):
    zip_bytes = _make_syslog_zip("Mar 10 11:55:00 test BG[1]: 1:01:01:when=1")
    response_ok_text_type = _FakeResponse(
        ok=True,
        status_code=200,
        text="all good",
        headers={"Content-Type": "text/plain"},
        chunks=[zip_bytes],
    )
    trigger.__dict__["client"] = SimpleNamespace(get_syslog=lambda: response_ok_text_type)

    path = trigger._download_syslog_zip()
    assert path is not None and path.exists()
    path.unlink()

    response_write_failure = _FakeResponse(
        ok=True,
        status_code=200,
        text="binary",
        headers={"Content-Type": "application/zip"},
        chunks=[RuntimeError("write failed")],
    )
    trigger.__dict__["client"] = SimpleNamespace(get_syslog=lambda: response_write_failure)

    with pytest.raises(RuntimeError):
        trigger._download_syslog_zip()


def test_iter_lines_skips_blank_lines_and_flush_empty_payload_branch(trigger):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
        zip_path = Path(tmp.name)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("syslog.log", "\nMar 10 11:55:00 test BG[1]: 1:01:01:when=1\n\n")

    try:
        lines = list(trigger._iter_syslog_lines(zip_path))
        assert lines == ["Mar 10 11:55:00 test BG[1]: 1:01:01:when=1"]
    finally:
        zip_path.unlink(missing_ok=True)

    incomplete_empty_parts = [
        "Mar 16 03:10:36 test BG[100]: 42:01:03:",
        "Mar 16 03:10:36 test BG[100]: 42:02:03:",
    ]
    assert list(iter_reassembled_records(incomplete_empty_parts)) == []


def test_fetch_events_batching_and_next_batch_empty_branch(trigger):
    trigger.configuration = cast(
        Any,
        BeyondTrustPRASyslogConfiguration(intake_key="intake_key", frequency=1).model_dump(),
    )

    lines = [
        "Mar 10 11:55:00 test BG[1]: 1:01:01:event=missing_when",
        "Mar 10 11:55:01 test BG[1]: 2:01:01:when=10;event=a",
        "Mar 10 11:55:02 test BG[1]: 3:01:01:when=10;event=b",
    ]
    for i in range(4, 1005):
        lines.append(f"Mar 10 11:55:03 test BG[1]: {i}:01:01:when={i};event=e{i}")

    zip_bytes = _make_syslog_zip("\n".join(lines) + "\n")

    with requests_mock.Mocker() as mock_requests:
        _mock_oauth(mock_requests)
        mock_requests.register_uri(
            "POST",
            "https://tenant.beyondtrustcloud.com/api/reporting",
            content=zip_bytes,
            headers={"Content-Type": "application/zip"},
        )

        trigger.from_date = 0
        batches = list(trigger.fetch_events())

    assert len(batches) == 2
    assert len(batches[0]) == 1000
    assert len(batches[1]) == 3

    with patch.object(trigger, "fetch_events", return_value=iter([[]])):
        with patch("beyondtrust_modules.connector_pra_syslog.time.time", side_effect=[0.0, 3.0]):
            with patch("beyondtrust_modules.connector_pra_syslog.time.sleep") as sleep_mock:
                trigger.next_batch()
                sleep_mock.assert_not_called()
