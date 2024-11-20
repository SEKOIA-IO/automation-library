from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from tehtris_modules import TehtrisModule
from tehtris_modules.trigger_tehtris_events import TehtrisEventConnector


@pytest.fixture
def fake_time():
    yield datetime(2022, 10, 19, 11, 59, 59, tzinfo=timezone.utc)


@pytest.fixture
def patch_datetime_now(fake_time):
    with patch("sekoia_automation.checkpoint.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_time
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)
        yield mock_datetime


@pytest.fixture
def trigger(symphony_storage, patch_datetime_now):
    module = TehtrisModule()
    trigger = TehtrisEventConnector(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {"apikey": "myapikey", "tenant_id": "abc"}
    trigger.configuration = {
        "intake_key": "intake_key",
        "filter_id": "uuid",
    }
    yield trigger


def message(event_id: int) -> dict[str, Any]:
    # flake8: noqa
    return {
        "rflId": 1,
        "time": "2022-10-19T12:00:00.163407+00:00",
        "lvl": 5,
        "module": "das",
        "eventName": "HeuristicAlert",
        "ipSrc": "1.2.3.4",
        "ipDst": "5.6.7.8",
        "egKBId": 110000031301810,
        "description": "Suspect spawn tree detected\n─ (Example\\doe-j) C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe (24644)\n── (Example\\doe-j) C:\\Windows\\System32\\cmd.exe (24876)\n\nNo remediation taken",
        "os_release__": "11",
        "pid": 24876,
        "domain__": "example.org",
        "os_version__": "10.0.22621",
        "cmdline": 'C:\\WINDOWS\\system32\\cmd.exe /d /c "C:\\Users\\doe-j\\AppData\\Local\\Programs\\IT Hit\\IT Hit Edit Doc Opener Host 5\\NativeHost.exe" chrome-extension://mdfaonmaoigngflemfmkboffllkopopm/ --parent-window=0 < \\\\.\\pipe\\LOCAL\\edge.nativeMessaging.in.c7c2f388b0eb2f77 > \\\\.\\pipe\\LOCAL\\edge.nativeMessaging.out.c7c2f388b0eb2f77',
        "username": "Example\\doe-j",
        "pCreateDatetime": "2022-10-19T12:00:00.098346+00:00",
        "location": "",
        "os_server__": False,
        "sha256": "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b",
        "ppid": 24644,
        "uuid__": "3be682e9-5568-4dbf-8e2d-5b36159945da",
        "path": "C:\\Windows\\System32\\cmd.exe",
        "tag": "YBE_PDT_WIN",
        "uid": "65470575-d8d5-4c54-80ca-a5e33c7e3dbe;windows;HOST01;example.org",
        "os__": "windows",
        "os_architecture__": "x86_64",
        "hostname__": "HOST01",
        "id": event_id,
    }


@pytest.fixture
def message1():
    # flake8: noqa
    return {
        "rflId": 1,
        "time": "2022-10-19T12:00:00.163407+00:00",
        "lvl": 5,
        "module": "das",
        "eventName": "HeuristicAlert",
        "ipSrc": "1.2.3.4",
        "ipDst": "5.6.7.8",
        "egKBId": 110000031301810,
        "description": "Suspect spawn tree detected\n─ (Example\\doe-j) C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe (24644)\n── (Example\\doe-j) C:\\Windows\\System32\\cmd.exe (24876)\n\nNo remediation taken",
        "os_release__": "11",
        "pid": 24876,
        "domain__": "example.org",
        "os_version__": "10.0.22621",
        "cmdline": 'C:\\WINDOWS\\system32\\cmd.exe /d /c "C:\\Users\\doe-j\\AppData\\Local\\Programs\\IT Hit\\IT Hit Edit Doc Opener Host 5\\NativeHost.exe" chrome-extension://mdfaonmaoigngflemfmkboffllkopopm/ --parent-window=0 < \\\\.\\pipe\\LOCAL\\edge.nativeMessaging.in.c7c2f388b0eb2f77 > \\\\.\\pipe\\LOCAL\\edge.nativeMessaging.out.c7c2f388b0eb2f77',
        "username": "Example\\doe-j",
        "pCreateDatetime": "2022-10-19T12:00:00.098346+00:00",
        "location": "",
        "os_server__": False,
        "sha256": "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b",
        "ppid": 24644,
        "uuid__": "3be682e9-5568-4dbf-8e2d-5b36159945da",
        "path": "C:\\Windows\\System32\\cmd.exe",
        "tag": "YBE_PDT_WIN",
        "uid": "3be682e9-5568-4dbf-8e2d-5b36159945da;windows;HOST01;example.org",
        "os__": "windows",
        "os_architecture__": "x86_64",
        "hostname__": "HOST01",
        "id": 111111111,
    }
    # flake8: qa


@pytest.fixture
def message2():
    # flake8: noqa
    return {
        "rflId": 1,
        "time": "2022-10-19T12:00:00.291503+00:00",
        "lvl": 6,
        "module": "das",
        "eventName": "HeuristicAlert",
        "ipSrc": "1.2.3.4",
        "ipDst": "5.6.7.8",
        "egKBId": 130171010000001,
        "description": "Application policy: COPS WINDOWS v2 ([I] T1204.001 User Execution: Web requests from unusual sources)",
        "os_release__": "10",
        "pid": 6112,
        "domain__": "example.org",
        "os_version__": "10.0.19041",
        "cmdline": '"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\106.0.1370.47\\identity_helper.exe" --type=utility --utility-sub-type=winrt_app_id.mojom.WinrtAppIdService --lang=fr --service-sandbox-type=none --unsafely-treat-insecure-origin-as-secure=http://sub1.example.org,http://sub1.example.org,http://sub2.example.org,http://sub2.example.org --mojo-platform-channel-handle=3576 --field-trial-handle=2084,i,10143906281170273548,16441631952397009556,131072 /prefetch:8',
        "username": "EXAMPLE\\doe-ja",
        "pCreateDatetime": "2022-10-19T12:00:00.119948+00:00",
        "location": "",
        "os_server__": False,
        "sha256": "01ba4719c80b6fe911b091a7c05124b64eeece964e09c058ef8f9805daca546b",
        "ppid": 15872,
        "uuid__": "ca5e55c2-85b5-4cdf-a585-1219f502b3e6",
        "path": "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\106.0.1370.47\\identity_helper.exe",
        "tag": "YBE_PDT_WIN",
        "uid": "ca5e55c2-85b5-4cdf-a585-1219f502b3e6;windows;HOST02;example.org",
        "os__": "windows",
        "os_architecture__": "x86_64",
        "hostname__": "HOST02",
        "id": 222222222,
    }
    # flake8: qa


def test_fetch_events(trigger, message1, message2):
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://abc.api.tehtris.net/api/xdr/v1/event",
            status_code=200,
            json=[message1, message2],
        )

        assert next(trigger.fetch_events()) == [message1, message2]


def test_fetch_events_without_duplicates(trigger, message1, message2):
    with requests_mock.Mocker() as mock:
        first_batch = [
            message(1),
            message(2),
            message(3),
        ]

        second_batch = [
            message(2),
            message(3),
            message(4),
            message(5),
        ]

        mock.get(
            "https://abc.api.tehtris.net/api/xdr/v1/event",
            status_code=200,
            json=first_batch,
        )

        result_first = next(trigger.fetch_events())
        assert [event["id"] for event in result_first] == [1, 2, 3]

        assert trigger.events_cache == {
            1: None,
            2: None,
            3: None,
        }

        mock.get(
            "https://abc.api.tehtris.net/api/xdr/v1/event",
            status_code=200,
            json=second_batch,
        )

        result_second = next(trigger.fetch_events())

        assert [event["id"] for event in result_second] == [4, 5]
        assert len(result_second) == 2


def test_fetch_events_pagination(trigger, message1, message2):
    first_batch = [message1] * 100
    second_batch = [message2] * 25
    with requests_mock.Mocker() as mock:
        m1 = mock.get(
            "https://abc.api.tehtris.net/api/xdr/v1/event?fromDate=1666180739&limit=100&offset=0",
            status_code=200,
            json=first_batch,
        )
        m2 = mock.get(
            "https://abc.api.tehtris.net/api/xdr/v1/event?fromDate=1666180739&limit=100&offset=100",
            status_code=200,
            json=second_batch,
        )

        assert list(trigger.fetch_events()) == [first_batch, second_batch]
        assert mock.call_count == 2
        assert m1.call_count == 1
        assert m2.call_count == 1
        # assert the most recent seen date was updated
        assert trigger.from_date == datetime(2022, 10, 19, 12, 0, 0, 291503, timezone.utc)


def test_next_batch_sleep_until_next_batch(trigger, message1, message2):
    with requests_mock.Mocker() as mock, patch("tehtris_modules.trigger_tehtris_events.time") as mock_time:
        mock.get(
            "https://abc.api.tehtris.net/api/xdr/v1/event",
            status_code=200,
            json=[message1, message2],
        )
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_long_next_batch_should_not_sleep(trigger, message1, message2):
    with requests_mock.Mocker() as mock, patch("tehtris_modules.trigger_tehtris_events.time") as mock_time:
        mock.get(
            "https://abc.api.tehtris.net/api/xdr/v1/event",
            status_code=200,
            json=[message1, message2],
        )
        batch_duration = trigger.configuration.frequency + 20  # the batch lasts more than the frequency
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0


def test_next_batch_with_small_chunk_size(symphony_storage, message1, message2):
    module = TehtrisModule()
    trigger = TehtrisEventConnector(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {"apikey": "myapikey", "tenant_id": "abc"}
    trigger.configuration = {"intake_key": "intake_key", "chunk_size": 2}
    with requests_mock.Mocker() as mock, patch("tehtris_modules.trigger_tehtris_events.time") as mock_time:
        mock.get(
            "https://abc.api.tehtris.net/api/xdr/v1/event",
            status_code=200,
            json=[message1, message2, message1],
        )
        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 2


def test_fetch_events_with_alternative_url(symphony_storage, patch_datetime_now, message1, message2):
    module = TehtrisModule()
    trigger = TehtrisEventConnector(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.module.configuration = {
        "apikey": "myapikey",
        "tenant_id": "abc",
        "alternative_url": "https://bde.api.tehtris.net:8443/api/",
    }
    trigger.configuration = {
        "intake_key": "intake_key",
        "filter_id": "uuid",
    }
    with requests_mock.Mocker() as mock:
        mock.get(
            "https://bde.api.tehtris.net:8443/api/xdr/v1/event",
            status_code=200,
            json=[message1, message2],
        )

        assert next(trigger.fetch_events()) == [message1, message2]
