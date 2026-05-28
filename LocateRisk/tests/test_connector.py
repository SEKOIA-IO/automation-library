from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from locaterisk_modules import LocateRiskModule
from locaterisk_modules.connector_locaterisk_scan_report import LocateRiskScanReportConnector

REPORT_URL = "https://app.locaterisk.com/api/rest/report/export"
SCAN_ID = "scan-123"
CSV_URL = f"{REPORT_URL}/{SCAN_ID}/csv"


@pytest.fixture
def connector(data_storage):
    module = LocateRiskModule()
    connector = LocateRiskScanReportConnector(module=module, data_path=data_storage)
    connector.log = MagicMock()
    connector.log_exception = MagicMock()
    connector.push_events_to_intakes = MagicMock()
    connector.module.configuration = {
        "api_key": "test-api-key",
        "scan_id": SCAN_ID,
        "report_url": REPORT_URL,
    }
    connector.configuration = {"intake_key": "intake-key", "polling_interval": 1}
    yield connector


def _stop_after_first_iteration(connector):
    """Patch time.sleep so the run() loop exits after one cycle."""

    def stop(_seconds):
        connector._stop_event.set()

    return patch("locaterisk_modules.connector_locaterisk_scan_report.time.sleep", side_effect=stop)


def test_run_pushes_parsed_csv_rows(connector):
    csv_body = (
        "host;cve;severity\r\n" "host-a;CVE-2024-0001;high\r\n" 'host-b;"CVE-2024-0002\nCVE-2024-0003";medium\r\n'
    )

    with requests_mock.Mocker() as mock_requests, _stop_after_first_iteration(connector):
        mock_requests.get(CSV_URL, status_code=200, text=csv_body)
        connector.run()

    connector.push_events_to_intakes.assert_called_once()
    events = connector.push_events_to_intakes.call_args.kwargs["events"]
    assert len(events) == 2
    # Each row is forwarded as a JSON string carrying the source tag.
    assert all('"source": "locaterisk"' in event for event in events)
    assert '"host": "host-a"' in events[0]
    assert "CVE-2024-0002\\nCVE-2024-0003" in events[1]


def test_run_skips_empty_rows(connector):
    csv_body = "host;cve\r\nhost-a;CVE-2024-0001\r\n;\r\n;\r\n"

    with requests_mock.Mocker() as mock_requests, _stop_after_first_iteration(connector):
        mock_requests.get(CSV_URL, status_code=200, text=csv_body)
        connector.run()

    connector.push_events_to_intakes.assert_called_once()
    events = connector.push_events_to_intakes.call_args.kwargs["events"]
    assert len(events) == 1


def test_run_no_push_when_response_empty(connector):
    with requests_mock.Mocker() as mock_requests, _stop_after_first_iteration(connector):
        mock_requests.get(CSV_URL, status_code=200, text="host;cve\r\n")
        connector.run()

    connector.push_events_to_intakes.assert_not_called()


def test_run_logs_exception_on_http_error(connector):
    with requests_mock.Mocker() as mock_requests, _stop_after_first_iteration(connector):
        mock_requests.get(CSV_URL, status_code=500, text="boom")
        connector.run()

    connector.push_events_to_intakes.assert_not_called()
    connector.log_exception.assert_called_once()


def test_run_handles_utf8_bom(connector):
    csv_body = "﻿host;cve\r\nhost-a;CVE-2024-0001\r\n"

    with requests_mock.Mocker() as mock_requests, _stop_after_first_iteration(connector):
        mock_requests.get(CSV_URL, status_code=200, text=csv_body)
        connector.run()

    events = connector.push_events_to_intakes.call_args.kwargs["events"]
    assert '"host": "host-a"' in events[0]
