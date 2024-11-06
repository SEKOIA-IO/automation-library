import os
import queue
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import orjson
import pytest
import requests.exceptions
import requests_mock

from crowdstrike_falcon import CrowdStrikeFalconModule
from crowdstrike_falcon.client import CrowdstrikeFalconClient, CrowdstrikeThreatGraphClient
from crowdstrike_falcon.event_stream_trigger import (
    EventForwarder,
    EventStreamReader,
    EventStreamTrigger,
    VerticlesCollector,
)


@pytest.fixture
def trigger(symphony_storage):
    module = CrowdStrikeFalconModule()
    trigger = EventStreamTrigger(module=module, data_path=symphony_storage)
    trigger.use_alert_api = False
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.module.configuration = {
        "base_url": "https://my.fake.sekoia",
        "client_id": "foo",
        "client_secret": "bar",
    }
    trigger.configuration = {
        "tg_username": "username",
        "tg_password": "password",
        "intake_key": "intake_key",
        "tg_base_url": "https://my.fake.sekoia",
    }
    trigger.app_id = "sio-00000"
    return trigger


def test_read_queue(trigger):
    trigger.events_queue.put(("fake-stream-url", '{"metadata": {"offset": 10}, "foo": "bar"}'))

    trigger.push_events_to_intakes = MagicMock()
    t = EventForwarder(trigger)
    t.start()

    time.sleep(2)

    t.stop()
    t.join()

    assert len(trigger.push_events_to_intakes.call_args.kwargs["events"]) == 1


def test_get_streams(trigger):
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/sensors/entities/datafeed/v2?appId=sio-00000",
            json={
                "errors": [],
                "meta": {
                    "query_time": 0.008346086,
                    "trace_id": "13787250-fc0f-49a6-9191-d809e30afdfb",
                },
                "resources": [{"dataFeedURL": "stream?q=1"}],
            },
        )

        streams = trigger.get_streams("sio-00000")
        assert streams == {"stream": {"dataFeedURL": "stream?q=1"}}


def test_authentication_exceed_ratelimit(trigger):
    with requests_mock.Mocker() as mock, patch("crowdstrike_falcon.event_stream_trigger.time.sleep") as mock_time:
        mock.register_uri("POST", "https://my.fake.sekoia/oauth2/token", status_code=429)

        trigger.stop()
        trigger.run()
        mock_time.assert_called_once_with(60)


def test_refresh_stream(trigger):
    refresh_url = "https://my.fake.sekoia/oauth2/token"

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            refresh_url,
            [
                {
                    "json": {
                        "access_token": "foo-token",
                        "token_type": "bearer",
                        "expires_in": 1799,
                    }
                },
                {"json": {}},
            ],
        )
        reader = EventStreamReader(
            trigger,
            "",
            {"refreshActiveSessionInterval": "50", "refreshActiveSessionURL": "https://my.fake.sekoia/oauth2/token"},
            "sio-00000",
        )

        reader.refresh_stream(refresh_url)


def test_refresh_stream_failed(trigger):
    refresh_url = "https://my.fake.sekoia/refresh_url"

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/oauth2/token",
            [
                {
                    "json": {
                        "access_token": "foo-token",
                        "token_type": "bearer",
                        "expires_in": 1799,
                    }
                },
                {"json": {}},
            ],
        )
        mock.register_uri("POST", refresh_url, status_code=500, text="Internal error")
        reader = EventStreamReader(
            trigger,
            "",
            {"refreshActiveSessionInterval": "50", "refreshActiveSessionURL": "https://my.fake.sekoia/refresh_url"},
            "sio-00000",
        )

        reader.refresh_stream(refresh_url)
        assert trigger.log.called


def test_read_stream(trigger):
    fake_stream = {
        "dataFeedURL": "https://firehose.eu-1.crowdstrike.com/sensors/entities/datafeed/v1/0?appId=sio-00000",
        "sessionToken": {
            "token": "my_token==",
            "expiration": "2022-07-06T12:39:24.017018689Z",
        },
        "refreshActiveSessionURL": (
            "https://api.eu-1.crowdstrike.com/sensors/entities/datafeed-actions"
            "/v1/0?appId=sio-00000&action_name=refresh_active_stream_session"
        ),
        "refreshActiveSessionInterval": 1800,
    }

    fake_event = {
        "metadata": {
            "customerIDString": "11111111111111111111111111111111",
            "offset": 174,
            "eventType": "AuthActivityAuditEvent",
            "eventCreationTime": 1657110865303,
            "version": "1.0",
        },
        "event": {
            "UserId": "api-client-id:00000000000000000000000000000000",
            "UserIp": "185.162.177.26",
            "OperationName": "streamStarted",
            "ServiceName": "Crowdstrike Streaming API",
            "Success": True,
            "UTCTimestamp": 1657110865,
            "AuditKeyValues": [
                {"Key": "partition", "ValueString": "0"},
                {"Key": "offset", "ValueString": "-1"},
                {"Key": "appId", "ValueString": "sio-00000"},
                {"Key": "eventType", "ValueString": "All event type(s)"},
                {
                    "Key": "APIClientID",
                    "ValueString": "22222222222222222222222222222222",
                },
            ],
        },
    }

    client_mock = MagicMock()
    client_mock.get.return_value.__enter__.return_value.status_code = 200
    client_mock.get.return_value.__enter__.return_value.iter_lines.return_value = [orjson.dumps(fake_event)]
    reader = EventStreamReader(
        trigger, fake_stream["dataFeedURL"].split("?")[0], fake_stream, 0, "sio-00000", client_mock
    )

    reader.start()

    time.sleep(1)
    reader.stop()
    reader.join()

    assert trigger.events_queue.qsize() > 1
    assert trigger.events_queue.get() == (
        "https://firehose.eu-1.crowdstrike.com/sensors/entities/datafeed/v1/0",
        orjson.dumps(fake_event).decode(),
    )


def test_read_stream_call_verticles_collector(trigger):
    fake_stream = {
        "dataFeedURL": "https://firehose.eu-1.crowdstrike.com/sensors/entities/datafeed/v1/0?appId=sio-00000",
        "sessionToken": {
            "token": "my_token==",
            "expiration": "2022-07-06T12:39:24.017018689Z",
        },
        "refreshActiveSessionURL": (
            "https://api.eu-1.crowdstrike.com/sensors/entities/datafeed-actions"
            "/v1/0?appId=sio-00000&action_name=refresh_active_stream_session"
        ),
        "refreshActiveSessionInterval": 1800,
    }

    detection_id = "ldt:00000000000000000000000000000000:1111111111"
    fake_event = {
        "metadata": {
            "customerIDString": "11111111111111111111111111111111",
            "offset": 1411586,
            "eventType": "DetectionSummaryEvent",
            "eventCreationTime": 1664892972000,
            "version": "1.0",
        },
        "event": {
            "DetectName": "Authentication Bypass",
            "SensorId": "445f78e41b0d4a2d962fb5991537081a",
            "DetectId": detection_id,
        },
    }

    client_mock = MagicMock()
    client_mock.get.return_value.__enter__.return_value.status_code = 200
    client_mock.get.return_value.__enter__.return_value.iter_lines.return_value = [orjson.dumps(fake_event)]
    verticles_collector = MagicMock()
    reader = EventStreamReader(
        trigger,
        fake_stream["dataFeedURL"].split("?")[0],
        fake_stream,
        "sio-00000",
        0,
        client_mock,
        verticles_collector,
    )

    reader.start()

    time.sleep(1)
    reader.stop()
    reader.join()

    assert trigger.events_queue.qsize() > 1
    assert trigger.events_queue.get() == (
        "https://firehose.eu-1.crowdstrike.com/sensors/entities/datafeed/v1/0",
        orjson.dumps(fake_event).decode(),
    )
    verticles_collector.collect_verticles_from_detection.assert_called_with(detection_id)


def test_read_stream_fails_on_stream_error(trigger):
    fake_stream = {
        "dataFeedURL": "https://firehose.eu-1.crowdstrike.com/sensors/entities/datafeed/v1/0?appId=sio-00000",
        "sessionToken": {
            "token": "my_token==",
            "expiration": "2022-07-06T12:39:24.017018689Z",
        },
        "refreshActiveSessionURL": (
            "https://api.eu-1.crowdstrike.com/sensors/entities/datafeed-actions"
            "/v1/0?appId=sio-00000&action_name=refresh_active_stream_session"
        ),
        "refreshActiveSessionInterval": 1800,
    }

    trigger.auth_token_refreshed_at = datetime.utcnow()
    client_mock = MagicMock()
    client_mock.get.return_value.__enter__.return_value.status_code = 400
    reader = EventStreamReader(
        trigger, fake_stream["dataFeedURL"].split("?")[0], fake_stream, "sio-00000", 0, client_mock
    )

    with pytest.raises(Exception):  # noqa: B017
        reader.run()

    reader.stop_refresh()
    assert trigger.events_queue.qsize() == 0


def test_run(trigger, symphony_storage):
    trigger.push_events_to_intakes = MagicMock()
    trigger.get_streams = MagicMock(
        return_value={
            "https://firehose.eu-1.crowdstrike.com/sensors/entities/datafeed/v1/0": {
                "dataFeedURL": (
                    "https://firehose.eu-1.crowdstrike.com/sensors/entities/datafeed/v1/0?appId=sio-00000"
                ),
                "refreshActiveSessionInterval": 1800,
                "refreshActiveSessionURL": (
                    "https://api.eu-1.crowdstrike.com/sensors/entities/"
                    "datafeed-actions/v1/0?appId=sio-00000&action_name=refresh_active_stream_session"
                ),
                "sessionToken": {
                    "expiration": "2022-07-05T13:44:46.890019143Z",
                    "token": "my-test-token=",
                },
            }
        }
    )
    trigger.stop()

    with patch("crowdstrike_falcon.event_stream_trigger.EventStreamReader"), requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/threatgraph/queries/edge-types/v1",
            json={
                "resources": [
                    "child_process",
                ]
            },
        )
        trigger.run()


def test_read_stream_consider_offset(trigger):
    fake_stream = {
        "dataFeedURL": "https://firehose.eu-1.crowdstrike.com/sensors/entities/datafeed/v1/0?appId=sio-00000",
        "sessionToken": {
            "token": "my_token==",
            "expiration": "2022-07-06T12:39:24.017018689Z",
        },
        "refreshActiveSessionURL": (
            "https://api.eu-1.crowdstrike.com/sensors/entities/datafeed-actions"
            "/v1/0?appId=sio-00000&action_name=refresh_active_stream_session"
        ),
        "refreshActiveSessionInterval": 1800,
    }

    trigger.auth_token_refreshed_at = datetime.utcnow()
    client_mock = MagicMock()
    client_mock.get.return_value.__enter__.return_value.status_code = 200
    reader = EventStreamReader(
        trigger, fake_stream["dataFeedURL"].split("?")[0], fake_stream, "sio-00000", 100, client_mock
    )
    reader.stop()
    reader.run()

    reader.stop_refresh()

    assert client_mock.get.call_args.kwargs.get("url") == (
        "https://firehose.eu-1.crowdstrike.com/sensors/entities/datafeed/v1/0?appId=sio-00000&offset=100"
    )


@pytest.mark.skipif(
    "{'CROWDSTRIKE_CLIENT_ID', 'CROWDSTRIKE_CLIENT_SECRET', 'CROWDSTRIKE_BASE_URL'}"
    ".issubset(os.environ.keys()) == False"
)
def test_read_stream_integration(symphony_storage):
    module = CrowdStrikeFalconModule()
    trigger = EventStreamTrigger(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.module.configuration = {
        "base_url": os.environ["CROWDSTRIKE_BASE_URL"],
        "client_id": os.environ["CROWDSTRIKE_CLIENT_ID"],
        "client_secret": os.environ["CROWDSTRIKE_CLIENT_SECRET"],
    }
    trigger.configuration = {
        "frequency": 0,
        "intake_key": "0123456789",
        "tg_username": os.environ.get("CROWDSTRIKE_FALCON_USERNAME"),
        "tg_password": os.environ.get("CROWDSTRIKE_FALCON_PASSWORD"),
        "tg_base_url": os.environ.get("CROWDSTRIKE_BASE_URL", "https://falconapi.eu-1.crowdstrike.com"),
    }
    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()

    streams: dict[str, dict] = trigger.get_streams()
    stream_root_url, stream_info = list(streams.items())[0]

    read_stream_thread = EventStreamReader(
        trigger,
        stream_root_url,
        stream_info,
        "sio-00000",
        client=trigger.client,
        verticles_collector=trigger.verticles_collector,
    )
    read_stream_thread.start()

    # wait few seconds
    time.sleep(5)
    read_stream_thread.stop()

    assert trigger.events_queue.qsize() > 0


@pytest.fixture
def verticles_collector(trigger):
    tg_client = CrowdstrikeThreatGraphClient(
        trigger.configuration.tg_base_url,
        trigger.configuration.tg_username,
        trigger.configuration.tg_password,
    )
    falcon_client = CrowdstrikeFalconClient(
        trigger.module.configuration.base_url,
        trigger.module.configuration.client_id,
        trigger.module.configuration.client_secret,
    )
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/threatgraph/queries/edge-types/v1",
            json={
                "resources": [
                    "child_process",
                ]
            },
        )
        yield VerticlesCollector(trigger, tg_client, falcon_client)


def test_verticle_collector_get_graph_ids_from_detection(verticles_collector):
    detection_details = {
        "behaviors": [
            {
                "control_graph_id": "ctg:835449907c99453085a924a16e967be5:17212155109",
                "objective": "Falcon Detection Method",
                "parent_details": {
                    "parent_process_graph_id": "pid:835449907c99453085a924a16e967be5:58913928",
                },
                "scenario": "suspicious_activity",
                "severity": 50,
                "timestamp": "2022-07-28T13:01:25Z",
                "triggering_process_graph_id": "pid:835449907c99453085a924a16e967be5:27242182487",
            }
        ],
        "detection_id": "ldt:835449907c99453085a924a16e967be5:17212155109",
        "first_behavior": "2022-07-28T13:01:25Z",
        "last_behavior": "2022-07-28T13:01:25Z",
    }

    assert verticles_collector.get_graph_ids_from_detection(detection_details) == {
        "pid:835449907c99453085a924a16e967be5:58913928",
        "pid:835449907c99453085a924a16e967be5:27242182487",
    }


def test_verticle_collector_get_graph_ids_from_alert(verticles_collector):
    alert_details = {
        "composite_id": "ad5f82e879a9c5d6b5b442eb37e50551:ind:835449907c99453085a924a16e967be5:17212155109-1-2",
        "control_graph_id": "ctg:835449907c99453085a924a16e967be5:17212155109",
        "parent_details": {
            "cmdline": "/usr/lib/git-core/git fetch --update-head-ok",
            "filename": "git",
            "filepath": "/usr/lib/git-core/git",
            "local_process_id": "1",
            "md5": "1bc29b36f623ba82aaf6724fd3b16718",
            "process_graph_id": "pid:835449907c99453085a924a16e967be5:27242182487",
            "process_id": "1",
            "sha256": "5d5b09f6dcb2d53a5fffc60c4ac0d55fabdf556069d6631545f42aa6e3500f2e",
            "timestamp": "2024-08-28T09:15:58Z",
            "user_graph_id": "uid:ee11cbb19052e40b07aac0ca060c23ee:0",
            "user_name": "root",
        },
        "triggering_process_graph_id": "pid:835449907c99453085a924a16e967be5:58913928",
        "type": "ldt",
        "updated_timestamp": "2024-08-28T11:32:04.582157884Z",
        "user_name": "root",
    }

    assert verticles_collector.get_graph_ids_from_alert(alert_details) == {
        "pid:835449907c99453085a924a16e967be5:58913928",
        "pid:835449907c99453085a924a16e967be5:27242182487",
    }


def test_verticle_collector_get_alert_details_wo_permissions(trigger, verticles_collector):
    trigger.use_alert_api = True

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/alerts/entities/alerts/v2",
            json={
                "meta": {
                    "query_time": 0.05286448,
                    "writes": {"resources_affected": 0},
                    "powered_by": "detectsapi",
                    "trace_id": "2d80bb22-a21b-4adc-ae09-e6e155f87eb9",
                },
                "errors": [
                    {
                        "code": 403,
                        "message": "don't have proper permissions",
                    }
                ],
                "resources": [],
            },
            status_code=403,
        )

        _ = list(verticles_collector.collect_verticles_from_alert(composite_id="id:123456"))
        assert trigger.use_alert_api is False


def test_verticle_collector_collect_verticles_from_graph_ids(verticles_collector):
    graph_ids = {
        "pid:835449907c99453085a924a16e967be5:8322695771",
        "pid:835449907c99453085a924a16e967be5:8302912087",
    }
    verticles1 = [
        {
            "id": "pid:835449907c99453085a924a16e967be5:6494700150",
            "customer_id": "11111111111111111111111111111111",
            "scope": "device",
            "object_id": "8322695771",
            "device_id": "22222222222222222222222222222222",
            "vertex_type": "process",
            "timestamp": "2022-07-30T20:22:29Z",
            "properties": {},
        },
        {
            "id": "pid:835449907c99453085a924a16e967be5:6492874271",
            "customer_id": "11111111111111111111111111111111",
            "scope": "device",
            "object_id": "8302912087",
            "device_id": "22222222222222222222222222222222",
            "vertex_type": "process",
            "timestamp": "2022-07-30T20:21:51Z",
            "properties": {},
        },
    ]
    verticles2 = [
        {
            "id": "pid:835449907c99453085a924a16e967be5:6463227462",
            "customer_id": "11111111111111111111111111111111",
            "scope": "device",
            "object_id": "6463227462",
            "device_id": "22222222222222222222222222222222",
            "vertex_type": "process",
            "timestamp": "2022-07-30T20:24:12Z",
            "properties": {},
        },
    ]
    verticles = [*verticles1, *verticles2]

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/threatgraph/combined/edges/v1?edge_type=child_process&ids=pid:835449907c99453085a924a16e967be5:8322695771",  # noqa: E501
            json={
                "errors": [],
                "meta": {},
                "resources": [
                    {
                        "edge_type": "child_process",
                        "id": "pid:835449907c99453085a924a16e967be5:6494700150",
                        "source_vertex_id": "pid:835449907c99453085a924a16e967be5:8322695771",
                    },
                    {
                        "edge_type": "child_process",
                        "id": "pid:835449907c99453085a924a16e967be5:6492874271",
                        "source_vertex_id": "pid:835449907c99453085a924a16e967be5:8322695771",
                    },
                ],
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/threatgraph/combined/edges/v1?edge_type=child_process&ids=pid:835449907c99453085a924a16e967be5:8302912087",  # noqa: E501
            json={
                "errors": [],
                "meta": {},
                "resources": [
                    {
                        "edge_type": "child_process",
                        "id": "pid:835449907c99453085a924a16e967be5:6463227462",
                        "source_vertex_id": "pid:835449907c99453085a924a16e967be5:8302912087",
                    }
                ],
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/threatgraph/entities/processes/v1?scope=device&"
            "ids=pid:835449907c99453085a924a16e967be5:6494700150&"
            "ids=pid:835449907c99453085a924a16e967be5:6492874271",
            json={
                "errors": [],
                "meta": {},
                "resources": verticles1,
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/threatgraph/entities/processes/v1?scope=device&ids=pid:835449907c99453085a924a16e967be5:6463227462",  # noqa: E501
            json={
                "errors": [],
                "meta": {},
                "resources": verticles2,
            },
        )

        collect = list(verticles_collector.collect_verticles_from_graph_ids(graph_ids))
        vertex_ids = {vertex["id"] for _, _, vertex in collect}
        assert vertex_ids == {vertex["id"] for vertex in verticles}


def test_read_stream_with_verticles(trigger):
    detection_id = "ldt:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:11111111111"

    stream = {
        "dataFeedURL": "https://my.fake.sekoia/sensors/entities/datafeed/v1/stream?q=1",
        "sessionToken": {
            "token": "my_token==",
            "expiration": "2022-07-06T12:39:24.017018689Z",
        },
        "refreshActiveSessionURL": (
            "https://my.fake.sekoia/sensors/entities/datafeed-actions"
            "/v1/0?appId=sio-00000&action_name=refresh_active_stream_session"
        ),
        "refreshActiveSessionInterval": 1800,
    }

    severity_code = 5
    severity_name = "Critical"
    event = {
        "metadata": {
            "customerIDString": "11111111111111111111111111111111",
            "offset": 174,
            "eventType": "DetectionSummaryEvent",
            "eventCreationTime": 1657110865303,
            "version": "1.0",
        },
        "event": {
            "ProcessStartTime": 1656688889,
            "ProcessEndTime": 0,
            "ProcessId": 22164474048,
            "ParentProcessId": 22163465296,
            "ComputerName": "nsewmkzevukn-vm",
            "UserName": "Administrator",
            "DetectName": "Overwatch Detection",
            "DetectDescription": "Falcon Overwatch has identified malicious activity carried out by a suspected or known eCrime operator. This activity has been raised for critical action and should be investigated urgently.",  # noqa: E501
            "Severity": severity_code,
            "SeverityName": severity_name,
            "FileName": "explorer.exe",
            "FilePath": "\\Device\\HarddiskVolume2\\Windows",
            "CommandLine": "C:\\Windows\\Explorer.EXE",
            "SHA256String": "249cb3cb46fd875196e7ed4a8736271a64ff2d8132357222a283be53e7232ed3",
            "MD5String": "d45bd7c7b7bf977246e9409d63435231",
            "SHA1String": "0000000000000000000000000000000000000000",
            "MachineDomain": "nsewmkzevukn-vm",
            "DetectId": detection_id,
        },
    }

    parent_process_graph_id = "pid:835449907c99453085a924a16e967be5:8322695771"
    triggering_process_graph_id = "pid:835449907c99453085a924a16e967be5:8302912087"
    detection = {
        "behaviors": [
            {
                "control_graph_id": "ctg:835449907c99453085a924a16e967be5:17212155109",
                "objective": "Falcon Detection Method",
                "parent_details": {
                    "parent_process_graph_id": parent_process_graph_id,
                },
                "scenario": "suspicious_activity",
                "severity": 50,
                "timestamp": "2022-07-28T13:01:25Z",
                "triggering_process_graph_id": triggering_process_graph_id,
            }
        ],
        "detection_id": "ldt:835449907c99453085a924a16e967be5:17212155109",
        "first_behavior": "2022-07-28T13:01:25Z",
        "last_behavior": "2022-07-28T13:01:25Z",
    }

    verticle1 = {
        "id": "pid:835449907c99453085a924a16e967be5:6494700150",
        "customer_id": "11111111111111111111111111111111",
        "scope": "device",
        "object_id": "8322695771",
        "device_id": "835449907c99453085a924a16e967be5",
        "vertex_type": "process",
        "timestamp": "2022-07-30T20:22:29Z",
        "properties": {},
    }
    verticle2 = {
        "id": "pid:835449907c99453085a924a16e967be5:6492874271",
        "customer_id": "11111111111111111111111111111111",
        "scope": "device",
        "object_id": "8302912087",
        "device_id": "835449907c99453085a924a16e967be5",
        "vertex_type": "process",
        "timestamp": "2022-07-30T20:21:51Z",
        "properties": {},
    }
    verticle3 = {
        "id": "pid:835449907c99453085a924a16e967be5:6463227462",
        "customer_id": "11111111111111111111111111111111",
        "scope": "device",
        "object_id": "6463227462",
        "device_id": "835449907c99453085a924a16e967be5",
        "vertex_type": "process",
        "timestamp": "2022-07-30T20:24:12Z",
        "properties": {},
    }

    edge_type = "child_process"
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/threatgraph/queries/edge-types/v1",
            json={
                "resources": [
                    "child_process",
                ]
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/sensors/entities/datafeed/v2?appId=sio-00000",
            json={
                "errors": [],
                "meta": {
                    "query_time": 0.008346086,
                    "trace_id": "13787250-fc0f-49a6-9191-d809e30afdfb",
                },
                "resources": [stream],
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/sensors/entities/datafeed/v1/stream?q=1",
            content=orjson.dumps(event) + b"\n",
        )

        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/detects/entities/summaries/GET/v1",
            json={
                "errors": [],
                "meta": {
                    "query_time": 0.008346086,
                    "trace_id": "13787250-fc0f-49a6-9191-d809e30afdfb",
                },
                "resources": [detection],
            },
        )

        mock.register_uri(
            "GET",
            f"https://my.fake.sekoia/threatgraph/combined/edges/v1?edge_type={edge_type}&ids={parent_process_graph_id}",  # noqa: E501
            json={
                "errors": [],
                "meta": {},
                "resources": [
                    {
                        "edge_type": edge_type,
                        "id": "pid:835449907c99453085a924a16e967be5:6494700150",
                        "source_vertex_id": parent_process_graph_id,
                    },
                    {
                        "edge_type": edge_type,
                        "id": "pid:835449907c99453085a924a16e967be5:6492874271",
                        "source_vertex_id": parent_process_graph_id,
                    },
                ],
            },
        )

        mock.register_uri(
            "GET",
            f"https://my.fake.sekoia/threatgraph/combined/edges/v1?edge_type={edge_type}&ids={triggering_process_graph_id}",  # noqa: E501
            json={
                "errors": [],
                "meta": {},
                "resources": [
                    {
                        "edge_type": edge_type,
                        "id": "pid:835449907c99453085a924a16e967be5:6463227462",
                        "source_vertex_id": triggering_process_graph_id,
                    }
                ],
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/threatgraph/entities/processes/v1?scope=device&"
            f"ids={verticle1['id']}&"
            f"ids={verticle2['id']}",
            json={
                "errors": [],
                "meta": {},
                "resources": [verticle1, verticle2],
            },
        )

        mock.register_uri(
            "GET",
            f"https://my.fake.sekoia/threatgraph/entities/processes/v1?scope=device&ids={verticle3['id']}",
            json={
                "errors": [],
                "meta": {},
                "resources": [verticle3],
            },
        )

        mock.register_uri(
            "POST",
            f"https://my.fake.sekoia/sensors/entities/datafeed-actions/v1/0?appId=sio-00000&action_name=refresh_active_stream_session",
            json={},
        )

        reader = EventStreamReader(
            trigger,
            stream["dataFeedURL"].split("?")[0],
            stream,
            "sio-00000",
            0,
            trigger.client,
            trigger.verticles_collector,
        )

        reader.start()

        time.sleep(1)
        reader.stop()
        reader.join()

        expected_verticles = [
            {
                "metadata": {
                    "detectionIdString": detection_id,
                    "eventType": "Vertex",
                    "edge": {
                        "sourceVertexId": parent_process_graph_id,
                        "type": edge_type,
                    },
                    "severity": {
                        "name": severity_name,
                        "code": severity_code,
                    },
                },
                "event": verticle1,
            },
            {
                "metadata": {
                    "detectionIdString": detection_id,
                    "eventType": "Vertex",
                    "edge": {
                        "sourceVertexId": parent_process_graph_id,
                        "type": edge_type,
                    },
                    "severity": {
                        "name": severity_name,
                        "code": severity_code,
                    },
                },
                "event": verticle2,
            },
            {
                "metadata": {
                    "detectionIdString": detection_id,
                    "eventType": "Vertex",
                    "edge": {
                        "sourceVertexId": triggering_process_graph_id,
                        "type": edge_type,
                    },
                    "severity": {
                        "name": severity_name,
                        "code": severity_code,
                    },
                },
                "event": verticle3,
            },
        ]
        expected_events = {orjson.dumps(msg).decode() for msg in (event, *expected_verticles)}

        assert trigger.events_queue.qsize() == len(expected_events)
        actual_events = set()
        try:
            while (msg := trigger.events_queue.get(timeout=1)) is not None:
                actual_events.add(msg[1])
        except queue.Empty:
            pass

        assert actual_events == expected_events


def test_read_stream_with_verticles_with_alert(trigger):
    trigger.use_alert_api = True
    detection_id = "ldt:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa:11111111111"

    stream = {
        "dataFeedURL": "https://my.fake.sekoia/sensors/entities/datafeed/v1/stream?q=1",
        "sessionToken": {
            "token": "my_token==",
            "expiration": "2022-07-06T12:39:24.017018689Z",
        },
        "refreshActiveSessionURL": (
            "https://my.fake.sekoia/sensors/entities/datafeed-actions"
            "/v1/0?appId=sio-00000&action_name=refresh_active_stream_session"
        ),
        "refreshActiveSessionInterval": 1800,
    }

    severity_code = 5
    severity_name = "Critical"
    event = {
        "metadata": {
            "customerIDString": "11111111111111111111111111111111",
            "offset": 174,
            "eventType": "EppDetectionSummaryEvent",
            "eventCreationTime": 1657110865303,
            "version": "1.0",
        },
        "event": {
            "ProcessStartTime": 1656688889,
            "ProcessEndTime": 0,
            "ProcessId": 22164474048,
            "ParentProcessId": 22163465296,
            "ComputerName": "nsewmkzevukn-vm",
            "UserName": "Administrator",
            "DetectName": "Overwatch Detection",
            "DetectDescription": "Falcon Overwatch has identified malicious activity carried out by a suspected or known eCrime operator. This activity has been raised for critical action and should be investigated urgently.",  # noqa: E501
            "Severity": severity_code,
            "SeverityName": severity_name,
            "FileName": "explorer.exe",
            "FilePath": "\\Device\\HarddiskVolume2\\Windows",
            "CommandLine": "C:\\Windows\\Explorer.EXE",
            "SHA256String": "249cb3cb46fd875196e7ed4a8736271a64ff2d8132357222a283be53e7232ed3",
            "MD5String": "d45bd7c7b7bf977246e9409d63435231",
            "SHA1String": "0000000000000000000000000000000000000000",
            "MachineDomain": "nsewmkzevukn-vm",
            "CompositeId": detection_id,
        },
    }

    parent_process_graph_id = "pid:835449907c99453085a924a16e967be5:8322695771"
    triggering_process_graph_id = "pid:835449907c99453085a924a16e967be5:8302912087"

    alert_details = {
        "composite_id": detection_id,
        "control_graph_id": "ctg:835449907c99453085a924a16e967be5:17212155109",
        "parent_details": {
            "cmdline": "/usr/lib/git-core/git fetch --update-head-ok",
            "filename": "git",
            "filepath": "/usr/lib/git-core/git",
            "local_process_id": "1",
            "md5": "1bc29b36f623ba82aaf6724fd3b16718",
            "process_graph_id": parent_process_graph_id,
            "process_id": "1",
            "sha256": "5d5b09f6dcb2d53a5fffc60c4ac0d55fabdf556069d6631545f42aa6e3500f2e",
            "timestamp": "2024-08-28T09:15:58Z",
            "user_graph_id": "uid:ee11cbb19052e40b07aac0ca060c23ee:0",
            "user_name": "root",
        },
        "triggering_process_graph_id": triggering_process_graph_id,
        "type": "ldt",
        "updated_timestamp": "2024-08-28T11:32:04.582157884Z",
        "user_name": "root",
    }

    verticle1 = {
        "id": "pid:835449907c99453085a924a16e967be5:6494700150",
        "customer_id": "11111111111111111111111111111111",
        "scope": "device",
        "object_id": "8322695771",
        "device_id": "835449907c99453085a924a16e967be5",
        "vertex_type": "process",
        "timestamp": "2022-07-30T20:22:29Z",
        "properties": {},
    }
    verticle2 = {
        "id": "pid:835449907c99453085a924a16e967be5:6492874271",
        "customer_id": "11111111111111111111111111111111",
        "scope": "device",
        "object_id": "8302912087",
        "device_id": "835449907c99453085a924a16e967be5",
        "vertex_type": "process",
        "timestamp": "2022-07-30T20:21:51Z",
        "properties": {},
    }
    verticle3 = {
        "id": "pid:835449907c99453085a924a16e967be5:6463227462",
        "customer_id": "11111111111111111111111111111111",
        "scope": "device",
        "object_id": "6463227462",
        "device_id": "835449907c99453085a924a16e967be5",
        "vertex_type": "process",
        "timestamp": "2022-07-30T20:24:12Z",
        "properties": {},
    }

    edge_type = "child_process"
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/threatgraph/queries/edge-types/v1",
            json={
                "resources": [
                    "child_process",
                ]
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/sensors/entities/datafeed/v2?appId=sio-00000",
            json={
                "errors": [],
                "meta": {
                    "query_time": 0.008346086,
                    "trace_id": "13787250-fc0f-49a6-9191-d809e30afdfb",
                },
                "resources": [stream],
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/sensors/entities/datafeed/v1/stream?q=1",
            content=orjson.dumps(event) + b"\n",
        )

        mock.register_uri(
            "POST",
            "https://my.fake.sekoia/alerts/entities/alerts/v2",
            json={
                "errors": [],
                "meta": {
                    "query_time": 0.008346086,
                    "trace_id": "13787250-fc0f-49a6-9191-d809e30afdfb",
                },
                "resources": [alert_details],
            },
        )

        mock.register_uri(
            "GET",
            f"https://my.fake.sekoia/threatgraph/combined/edges/v1?edge_type={edge_type}&ids={parent_process_graph_id}",  # noqa: E501
            json={
                "errors": [],
                "meta": {},
                "resources": [
                    {
                        "edge_type": edge_type,
                        "id": "pid:835449907c99453085a924a16e967be5:6494700150",
                        "source_vertex_id": parent_process_graph_id,
                    },
                    {
                        "edge_type": edge_type,
                        "id": "pid:835449907c99453085a924a16e967be5:6492874271",
                        "source_vertex_id": parent_process_graph_id,
                    },
                ],
            },
        )

        mock.register_uri(
            "GET",
            f"https://my.fake.sekoia/threatgraph/combined/edges/v1?edge_type={edge_type}&ids={triggering_process_graph_id}",  # noqa: E501
            json={
                "errors": [],
                "meta": {},
                "resources": [
                    {
                        "edge_type": edge_type,
                        "id": "pid:835449907c99453085a924a16e967be5:6463227462",
                        "source_vertex_id": triggering_process_graph_id,
                    }
                ],
            },
        )

        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/threatgraph/entities/processes/v1?scope=device&"
            f"ids={verticle1['id']}&"
            f"ids={verticle2['id']}",
            json={
                "errors": [],
                "meta": {},
                "resources": [verticle1, verticle2],
            },
        )

        mock.register_uri(
            "GET",
            f"https://my.fake.sekoia/threatgraph/entities/processes/v1?scope=device&ids={verticle3['id']}",
            json={
                "errors": [],
                "meta": {},
                "resources": [verticle3],
            },
        )

        mock.register_uri(
            "POST",
            f"https://my.fake.sekoia/sensors/entities/datafeed-actions/v1/0?appId=sio-00000&action_name=refresh_active_stream_session",
            json={},
        )

        reader = EventStreamReader(
            trigger,
            stream["dataFeedURL"].split("?")[0],
            stream,
            "sio-00000",
            0,
            trigger.client,
            trigger.verticles_collector,
        )

        reader.start()

        time.sleep(1)
        reader.stop()
        reader.join()

        expected_verticles = [
            {
                "metadata": {
                    "detectionIdString": detection_id,
                    "eventType": "Vertex",
                    "edge": {
                        "sourceVertexId": parent_process_graph_id,
                        "type": edge_type,
                    },
                    "severity": {
                        "name": severity_name,
                        "code": severity_code,
                    },
                },
                "event": verticle1,
            },
            {
                "metadata": {
                    "detectionIdString": detection_id,
                    "eventType": "Vertex",
                    "edge": {
                        "sourceVertexId": parent_process_graph_id,
                        "type": edge_type,
                    },
                    "severity": {
                        "name": severity_name,
                        "code": severity_code,
                    },
                },
                "event": verticle2,
            },
            {
                "metadata": {
                    "detectionIdString": detection_id,
                    "eventType": "Vertex",
                    "edge": {
                        "sourceVertexId": triggering_process_graph_id,
                        "type": edge_type,
                    },
                    "severity": {
                        "name": severity_name,
                        "code": severity_code,
                    },
                },
                "event": verticle3,
            },
        ]
        expected_events = {orjson.dumps(msg).decode() for msg in (event, *expected_verticles)}

        assert trigger.events_queue.qsize() == len(expected_events)
        actual_events = set()
        try:
            while (msg := trigger.events_queue.get(timeout=1)) is not None:
                actual_events.add(msg[1])
        except queue.Empty:
            pass

        assert actual_events == expected_events


def test_verticles_collector_with_invalid_credential(symphony_storage):
    module = CrowdStrikeFalconModule()
    trigger = EventStreamTrigger(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.module.configuration = {
        "base_url": "https://my.fake.sekoia",
        "client_id": "foo",
        "client_secret": "bar",
    }
    trigger.configuration = {
        "tg_username": "username",
        "tg_password": "password",
        "intake_key": "intake_key",
        "tg_base_url": "https://my.fake.sekoia",
    }
    trigger.app_id = "sio-00000"
    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://my.fake.sekoia/threatgraph/queries/edge-types/v1",
            status_code=401,
        )
        trigger.verticles_collector
