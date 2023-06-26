"""Additional programmatic configuration for pytest."""

import asyncio
from typing import List
from unittest.mock import patch

import pytest
from faker import Faker

from client.schemas.attributes.epo_events import EpoEventAttributes
from client.schemas.edr import TrellixEdrResponse
from client.schemas.token import HttpToken
from client.token_refresher import TrellixTokenRefresher


@pytest.fixture(scope="session")
def faker_locale() -> List[str]:
    """
    Configure Faker to use correct locale.

    Returns:
        List[str]:
    """
    return ["en"]


@pytest.fixture(scope="session")
def faker_seed() -> int:
    """
    Configure Faker to use correct seed.

    Returns:
        int:
    """
    return 123456


@pytest.fixture(scope="session")
def session_faker(faker_locale: List[str], faker_seed: int) -> Faker:
    """
    Configure session lvl Faker to use correct seed and locale.

    Args:
        faker_locale: List[str]
        faker_seed: int

    Returns:
        Faker:
    """
    instance = Faker(locale=faker_locale)
    instance.seed_instance(seed=faker_seed)

    return instance


@pytest.fixture
def http_token(session_faker) -> HttpToken:
    """
    Generate HttpToken.

    Args:
        session_faker: Faker

    Returns:
        HttpToken:
    """
    return HttpToken(
        tid=session_faker.pyint(),
        token_type=session_faker.word(),
        expires_in=session_faker.pyint(),
        access_token=session_faker.word(),
    )


@pytest.fixture
def token_refresher_session():
    """
    Mock session for TrellixTokenRefresher.

    Yields:
        MagicMock:
    """
    with patch.object(TrellixTokenRefresher, "_session") as session_mock:
        yield session_mock


@pytest.fixture
def edr_epo_event_response(session_faker) -> TrellixEdrResponse[EpoEventAttributes]:
    """
    Generate TrellixEdrResponse[EpoEventAttributes].

    Args:
        session_faker: Faker

    Returns:
        TrellixEdrResponse[EpoEventAttributes]:
    """
    return TrellixEdrResponse[EpoEventAttributes](
        id=session_faker.uuid4(),
        type=session_faker.word(),
        attributes=EpoEventAttributes(
            timestamp=session_faker.date_time(),
            autoguid=session_faker.word(),
            detectedutc="{0}".format(session_faker.date_time().timestamp()),
            receivedutc="{0}".format(session_faker.date_time().timestamp()),
            agentguid=session_faker.word(),
            analyzer=session_faker.word(),
            analyzername=session_faker.word(),
            analyzerversion=session_faker.word(),
            analyzerhostname=session_faker.word(),
            analyzeripv4=session_faker.ipv4(),
            analyzeripv6=session_faker.ipv6(),
            analyzermac=session_faker.word(),
            analyzerdatversion=session_faker.word(),
            analyzerengineversion=session_faker.word(),
            analyzerdetectionmethod=session_faker.word(),
            sourcehostname=session_faker.word(),
            sourceipv4=session_faker.ipv4(),
            sourceipv6=session_faker.ipv6(),
            sourcemac=session_faker.word(),
            sourceusername=session_faker.word(),
            sourceprocessname=session_faker.word(),
            sourceurl=session_faker.uri(),
            targethostname=session_faker.word(),
            targetipv4=session_faker.ipv4(),
            targetipv6=session_faker.ipv6(),
            targetmac=session_faker.word(),
            targetusername=session_faker.word(),
            targetport="{0}".format(session_faker.pyint()),
            targetprotocol=session_faker.word(),
            targetprocessname=session_faker.word(),
            targetfilename=session_faker.word(),
            threatcategory=session_faker.word(),
            threateventid=session_faker.pyint(),
            threatseverity=session_faker.word(),
            threatname=session_faker.word(),
            threattype=session_faker.word(),
            threatactiontaken=session_faker.word(),
            threathandled=session_faker.pybool(),
            nodepath=session_faker.word(),
            targethash=session_faker.word(),
            sourceprocesshash=session_faker.word(),
            sourceprocesssigned=session_faker.word(),
            sourceprocesssigner=session_faker.word(),
            sourcefilepath=session_faker.file_path(),
        ),
    )


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for pytest.mark.asyncio.

    Yields:
        loop:
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()

    yield loop

    loop.close()
