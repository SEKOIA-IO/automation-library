"""Tests to handle EDR alerts events."""

import orjson
import pytest
from faker import Faker

from client.schemas.attributes.edr_alerts import EdrAlertAttributes
from client.schemas.trellix_response import TrellixResponse


@pytest.mark.asyncio
async def test_edr_alert_events(session_faker: Faker):
    """
    Test EDR alert attributes.

    Args:
        session_faker:
    """
    expected_response = {
        "type": session_faker.word(),
        "id": session_faker.word(),
        "attributes": {
            "traceId": session_faker.word(),
            "parentTraceId": session_faker.word(),
            "rootTraceId": session_faker.word(),
            "aGuid": session_faker.word(),
            "detectionDate": session_faker.word(),
            "eventDate": session_faker.word(),
            "eventType": session_faker.word(),
            "severity": session_faker.word(),
            "score": session_faker.pyint(),
            "detectionTags": [session_faker.word(), session_faker.word()],
            "relatedTraceIds": [session_faker.word(), session_faker.word()],
            "ruleId": session_faker.word(),
            "rank": session_faker.pyint(),
            "pid": session_faker.pyint(),
            "version": session_faker.word(),
            "parentsTraceId": [session_faker.word(), session_faker.word()],
            "processName": session_faker.word(),
            "user": session_faker.word(),
            "cmdLine": session_faker.word(),
            "hashId": session_faker.word(),
            "h_os": session_faker.word(),
            "domain": session_faker.word(),
            "hostName": session_faker.word(),
        },
    }

    response = TrellixResponse[EdrAlertAttributes](**orjson.loads(orjson.dumps(expected_response).decode("utf-8")))

    assert isinstance(response, TrellixResponse)
    assert isinstance(response.attributes, EdrAlertAttributes)
    assert response.dict() == expected_response


@pytest.mark.asyncio
async def test_edr_alerts_events_1(session_faker):
    """
    Test EDR alert attributes.

    Args:
        session_faker:
    """
    api_docs_response = {
        "Trace_Id": "71d3a718-9095-494c-ada5-7134dbeaa564",
        "Parent_Trace_Id": "ffc4c8eb-6cf9-4b59-8416-b14d55d290dd",
        "Root_Trace_Id": "ffc4c8eb-6cf9-4b59-8416-b14d55d290dd",
        "DetectionDate": "2024-06-19T07:44:55.708+00:00",
        "Event_Date": "2024-06-19T07:43:17.567Z",
        "Activity": "Threat Detected",
        "Severity": "s0",
        "Score": 25,
        "Detection_Tags": [
            "@ATA.Execution",
            "@ATA.Persistence",
            "@ATA.PrivilegeEscalation",
            "@ATE.T1059",
            "@ATE.T1547.009",
            "@MSI._file_sysscript",
        ],
        "Related_Trace_Id": ["22ee44a6-3b26-4bb5-811e-c5e399069a64"],
        "RuleId": "_file_sysscript",
        "Rank": 25,
        "Pid": 6600,
        "Version": "undefined",
        "Parents_Trace_Id": [
            "ffc4c8eb-6cf9-4b59-8416-b14d55d290dd",
            "5824f090-791e-47d5-a5ba-3abcb4f9d2b9",
            "599463c2-7f27-41c0-a096-21de1018bfa8",
            "5e910e15-c8d4-4724-af28-09be2b48abd9",
        ],
        "ProcessName": "SDXHelper.exe",
        "User": {"domain": "CDA", "name": "cdaauto"},
        "CommandLine": '"C:\\Program Files\\Microsoft Office\\Root\\Office16\\SDXHelper.exe" -Embedding',
        "Hash_Id": "h7GhOs3Jm6Buj+LuzOOHBg==",
        "Host_OS": "windows",
        "Host_Name": "302W1022H264",
        "MAGUID": "ADB3C24C-232B-11EF-3D71-005056AC48D2",
        "Artifact": "Threat",
    }

    response = EdrAlertAttributes.parse_response(orjson.loads(orjson.dumps(api_docs_response).decode("utf-8")))

    assert isinstance(response, EdrAlertAttributes)
