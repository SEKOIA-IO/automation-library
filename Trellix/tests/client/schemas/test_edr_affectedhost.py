"""Tests to handle EDR affectedhost events."""

import orjson
import pytest
from faker import Faker

from client.schemas.attributes.edr_affectedhosts import EdrAffectedhostAttributes
from client.schemas.trellix_response import TrellixResponse


@pytest.mark.asyncio
async def test_edr_affectedhost_events(session_faker: Faker):
    """
    Test EDR affectedhost attributes.

    Args:
        session_faker:
    """
    expected_response = {
        "type": session_faker.word(),
        "attributes": {
            "detectionsCount": session_faker.pyint(),
            "severity": session_faker.word(),
            "rank": session_faker.pyint(),
            "firstDetected": session_faker.word(),
            "host": {session_faker.word(): session_faker.word(), session_faker.word(): session_faker.pyint()},
        },
    }

    response = TrellixResponse[EdrAffectedhostAttributes](
        **orjson.loads(orjson.dumps(expected_response).decode("utf-8")),
    )

    assert isinstance(response, TrellixResponse)
    assert isinstance(response.attributes, EdrAffectedhostAttributes)
    assert response.dict(exclude_none=True) == expected_response
