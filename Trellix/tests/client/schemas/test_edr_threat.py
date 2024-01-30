"""Tests to handle EDR threat events."""

import orjson
import pytest
from faker import Faker

from client.schemas.attributes.edr_threats import EdrThreatAttributes
from client.schemas.trellix_response import TrellixResponse


@pytest.mark.asyncio
async def test_edr_threat_events(session_faker: Faker):
    """
    Test EDR threat attributes.

    Args:
        session_faker:
    """
    expected_response = {
        "type": session_faker.word(),
        "id": session_faker.word(),
        "attributes": {
            "aggregationKey": session_faker.word(),
            "severity": session_faker.word(),
            "rank": session_faker.pyint(),
            "score": session_faker.pyint(),
            "name": session_faker.word(),
            "type": session_faker.word(),
            "status": session_faker.word(),
            "firstDetected": session_faker.word(),
            "lastDetected": session_faker.word(),
            "hashes": {
                session_faker.word(): session_faker.word(),
                session_faker.word(): session_faker.word(),
                session_faker.word(): session_faker.word(),
            },
            "interpreter": {
                session_faker.word(): session_faker.word(),
                session_faker.word(): session_faker.word(),
                session_faker.word(): session_faker.word(),
            },
        },
    }

    response = TrellixResponse[EdrThreatAttributes](**orjson.loads(orjson.dumps(expected_response).decode("utf-8")))

    assert isinstance(response, TrellixResponse)
    assert isinstance(response.attributes, EdrThreatAttributes)
    assert response.dict() == expected_response
