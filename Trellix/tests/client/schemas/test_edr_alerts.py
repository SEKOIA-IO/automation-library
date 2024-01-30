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
