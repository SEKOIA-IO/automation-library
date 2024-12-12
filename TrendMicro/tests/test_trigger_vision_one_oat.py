import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests_mock

from trendmicro_modules import TrendMicroModule
from trendmicro_modules.trigger_vision_one_oat import TrendMicroVisionOneOATConnector


@pytest.fixture
def trigger(symphony_storage):
    module = TrendMicroModule()
    trigger = TrendMicroVisionOneOATConnector(module=module, data_path=symphony_storage)

    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "base_url": "https://api.xdr.trendmicro.com",
        "api_key": "01234556789abcdef",
        "intake_key": "intake_key",
    }
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()

    return trigger


@pytest.fixture
def message_1():
    return {
        "totalCount": 0,
        "count": 0,
        "items": [
            {
                "source": "endpointActivityData",
                "uuid": "fdd69d98-58de-4249-9871-2e1b233b72ff",
                "filters": [
                    {
                        "id": "F4231",
                        "name": "Service Execution via Service Control Manager",
                        "description": "Service Control Manager (services.exe) has executed a process",
                        "mitreTacticIds": ["TA0002"],
                        "mitreTechniqueIds": ["T1560.002"],
                        "highlightedObjects": [{"type": "port", "field": "objectPort", "value": 443}],
                        "riskLevel": "info",
                        "type": "custom",
                    }
                ],
                "endpoint": {
                    "endpointName": "LAB-Luwak-1048",
                    "agentGuid": "cedddc75-d673-4ba0-a1f6-cf6b05a84670",
                    "ips": ["10.209.14.33", "fe80::8473:af77:b312:35ea"],
                },
                "entityType": "endpoint",
                "entityName": "desktop 1 (127.0.0.1) or 127.0.0.1 | xxxx@gmail.com | arn:aws:lambda:*:%s:function:%s | k8s_container-8c55678bd-8r7zt_default_4b291f63-c0e1-46e6-8503-ee2a834a876c_6411 | 6d7d30d2148a | -",
                "detectedDateTime": "2020-06-01T02:12:56Z",
                "ingestedDateTime": "2020-06-01T02:12:56Z",
                "detail": {
                    "eventTime": "1649806995000",
                    "tags": ["MITREV9.T1569.002", "XSAE.F4231"],
                    "uuid": "fdd69d98-58de-4249-9871-2e1b233b72ff",
                    "productCode": "xes",
                    "filterRiskLevel": "info",
                    "bitwiseFilterRiskLevel": 1,
                    "eventId": "1",
                    "eventSubId": 2,
                    "eventHashId": "-7817927890991207527",
                    "firstSeen": "1649806995000",
                    "lastSeen": "1649806995000",
                    "endpointGuid": "cedddc75-d673-4ba0-a1f6-cf6b05a84670",
                    "endpointHostName": "LAB-Luwak-1048",
                    "endpointIp": ["fe80::8473:af77:b312:35ea", "10.209.14.33"],
                    "endpointMacAddress": ["00:50:56:89:09:9b"],
                    "timezone": "UTC+08:00",
                    "pname": "751",
                    "pver": "1.2.0.2454",
                    "plang": 1,
                    "pplat": 5889,
                    "osName": "Windows",
                    "osVer": "10.0.19044",
                    "osDescription": "Windows 10 Enterprise (64 bit) build 19044",
                    "osType": "0x00000004",
                    "processHashId": "8149551095598764453",
                    "processName": "C:\\Windows\\System32\\services.exe",
                    "processPid": 672,
                    "sessionId": 0,
                    "processUser": "SYSTEM",
                    "processUserDomain": "NT AUTHORITY",
                    "processLaunchTime": "1646826182237",
                    "processCmd": "C:\\Windows\\system32\\services.exe",
                    "authId": "999",
                    "integrityLevel": 16384,
                    "processFileHashId": "-4092577940452904134",
                    "processFilePath": "C:\\Windows\\System32\\services.exe",
                    "processFileHashSha1": "d7a213f3cfee2a8a191769eb33847953be51de54",
                    "processFileHashSha256": "dfbea9e8c316d9bc118b454b0c722cd674c30d0a256340200e2c3a7480cba674",
                    "processFileHashMd5": "d8e577bf078c45954f4531885478d5a9",
                    "processSigner": ["Microsoft Windows Publisher"],
                    "processSignerValid": [True],
                    "processFileSize": "714856",
                    "processFileCreation": "1618396713939",
                    "processFileModifiedTime": "1618396713971",
                    "processTrueType": 7,
                    "objectHashId": "499492567380524547",
                    "objectUser": "NETWORK SERVICE",
                    "objectUserDomain": "NT AUTHORITY",
                    "objectSessionId": "0",
                    "objectFilePath": "C:\\Windows\\System32\\sppsvc.exe",
                    "objectFileHashSha1": "eee6e72ae3f5f739c22623ce8d99359ea35d6cc1",
                    "objectFileHashSha256": "9d7b36a9c7fa965880a6033f043116852a91730345560a596605d5f3fab1ab2b",
                    "objectFileHashMd5": "f0baaa4fa19e5e6169cd8ed0e7517dde",
                    "objectSigner": ["Microsoft Windows"],
                    "objectSignerValid": [True],
                    "objectFileSize": "4629328",
                    "objectFileCreation": "1646822883174",
                    "objectFileModifiedTime": "1646822883393",
                    "objectTrueType": 7,
                    "objectName": "C:\\Windows\\System32\\sppsvc.exe",
                    "objectPid": 3832,
                    "objectLaunchTime": "1649806995010",
                    "objectCmd": "C:\\Windows\\system32\\sppsvc.exe",
                    "objectAuthId": "996",
                    "objectIntegrityLevel": 16384,
                    "objectFileHashId": "-4729198244400997661",
                    "objectRunAsLocalAccount": False,
                },
            }
        ],
    }


def test_fetch_events(trigger, message_1):
    trigger.cursor.offset = datetime(year=2024, month=11, day=1, tzinfo=timezone.utc)
    with patch(
        "trendmicro_modules.trigger_vision_one_base.time"
    ) as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.register_uri("GET", "https://api.xdr.trendmicro.com/v3.0/oat/detections", json=message_1)

        batch_duration = 16  # the batch lasts 16 seconds
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 1


def test_long_next_batch_should_not_sleep(trigger, message_1):
    trigger.cursor.offset = datetime(year=2024, month=11, day=1, tzinfo=timezone.utc)
    with patch(
        "trendmicro_modules.trigger_vision_one_base.time"
    ) as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.register_uri("GET", "https://api.xdr.trendmicro.com/v3.0/oat/detections", json=message_1)

        batch_duration = trigger.configuration.frequency + 20  # the batch lasts more than the frequency
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0
