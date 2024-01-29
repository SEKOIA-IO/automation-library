"""Tests to handle EDR detection events."""

import orjson
import pytest
from faker import Faker

from client.schemas.attributes.edr_detections import EdrDetectionAttributes
from client.schemas.trellix_response import TrellixResponse


@pytest.mark.asyncio
async def test_edr_detection_events(session_faker: Faker):
    """
    Test EDR detection attributes.

    Args:
        session_faker:
    """
    expected_response = {
        "type": session_faker.word(),
        "attributes": {
            "traceId": session_faker.word(),
            "firstDetected": session_faker.word(),
            "severity": session_faker.word(),
            "rank": session_faker.pyint(),
            "tags": [session_faker.word(), session_faker.word()],
            "host": {
                session_faker.word(): session_faker.word(),
                session_faker.word(): session_faker.word(),
            },
            "sha256": session_faker.word(),
        },
    }

    response = TrellixResponse[EdrDetectionAttributes](**orjson.loads(orjson.dumps(expected_response).decode("utf-8")))

    assert isinstance(response, TrellixResponse)
    assert isinstance(response.attributes, EdrDetectionAttributes)
    assert response.dict(exclude_none=True) == expected_response
