"""Tests to handle EPO events."""

import orjson
import pytest
from faker import Faker

from client.schemas.attributes.epo_events import EpoEventAttributes
from client.schemas.trellix_response import TrellixResponse


@pytest.mark.asyncio
async def test_epo_events(session_faker: Faker):
    """
    Test epo events attributes.

    Args:
        session_faker: Faker
    """
    expected_response = {
        "type": session_faker.word(),
        "id": session_faker.word(),
        "attributes": {
            "timestamp": session_faker.date_time(),
            "autoguid": session_faker.word(),
            "detectedutc": "{0}".format(session_faker.date_time().timestamp()),
            "receivedutc": "{0}".format(session_faker.date_time().timestamp()),
            "agentguid": session_faker.word(),
            "analyzer": session_faker.word(),
            "analyzername": session_faker.word(),
            "analyzerversion": session_faker.word(),
            "analyzerhostname": session_faker.word(),
            "analyzeripv4": session_faker.ipv4(),
            "analyzeripv6": session_faker.ipv6(),
            "analyzermac": session_faker.word(),
            "analyzerdatversion": session_faker.word(),
            "analyzerengineversion": session_faker.word(),
            "analyzerdetectionmethod": session_faker.word(),
            "sourcehostname": session_faker.word(),
            "sourceipv4": session_faker.ipv4(),
            "sourceipv6": session_faker.ipv6(),
            "sourcemac": session_faker.word(),
            "sourceusername": session_faker.word(),
            "sourceprocessname": session_faker.word(),
            "sourceurl": session_faker.uri(),
            "targethostname": session_faker.word(),
            "targetipv4": session_faker.ipv4(),
            "targetipv6": session_faker.ipv6(),
            "targetmac": session_faker.word(),
            "targetusername": session_faker.word(),
            "targetport": "{0}".format(session_faker.pyint()),
            "targetprotocol": session_faker.word(),
            "targetprocessname": session_faker.word(),
            "targetfilename": session_faker.word(),
            "threatcategory": session_faker.word(),
            "threateventid": session_faker.pyint(),
            "threatseverity": session_faker.word(),
            "threatname": session_faker.word(),
            "threattype": session_faker.word(),
            "threatactiontaken": session_faker.word(),
            "threathandled": session_faker.pybool(),
            "nodepath": session_faker.word(),
            "targethash": session_faker.word(),
            "sourceprocesshash": session_faker.word(),
            "sourceprocesssigned": session_faker.word(),
            "sourceprocesssigner": session_faker.word(),
            "sourcefilepath": session_faker.file_path(),
        },
    }

    response = TrellixResponse[EpoEventAttributes](**orjson.loads(orjson.dumps(expected_response).decode("utf-8")))

    assert isinstance(response, TrellixResponse)
    assert isinstance(response.attributes, EpoEventAttributes)
    assert response.dict() == expected_response
