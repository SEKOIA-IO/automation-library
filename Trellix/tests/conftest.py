"""Additional programmatic configuration for pytest."""

import asyncio
from shutil import rmtree
from tempfile import mkdtemp
from typing import Any, List
from unittest.mock import patch

import pytest
from faker import Faker
from sekoia_automation import constants

from client.schemas.attributes.edr_affectedhosts import EdrAffectedhostAttributes
from client.schemas.attributes.edr_alerts import EdrAlertAttributes
from client.schemas.attributes.edr_detections import EdrDetectionAttributes
from client.schemas.attributes.edr_threats import EdrThreatAttributes
from client.schemas.attributes.epo_events import EpoEventAttributes
from client.schemas.token import HttpToken
from client.schemas.trellix_response import TrellixResponse
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
        expires_in=session_faker.pyint(min_value=500, max_value=1000),
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
def symphony_storage() -> str:
    """
    Fixture for symphony temporary storage.

    Yields:
        str:
    """
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield constants.DATA_STORAGE

    rmtree(constants.DATA_STORAGE)
    constants.SYMPHONY_STORAGE = original_storage


@pytest.fixture
def epo_event_response(session_faker) -> TrellixResponse[EpoEventAttributes]:
    """
    Generate TrellixEdrResponse[EpoEventAttributes].

    Args:
        session_faker: Faker

    Returns:
        TrellixResponse[EpoEventAttributes]:
    """
    return TrellixResponse[EpoEventAttributes](
        id=session_faker.uuid4(),
        type=session_faker.word(),
        attributes=EpoEventAttributes(
            timestamp=session_faker.date_time(),
            autoguid=session_faker.word(),
            detectedutc=session_faker.date_time().isoformat(),
            receivedutc=session_faker.date_time().isoformat(),
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
            targetport=str(session_faker.pyint()),
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


@pytest.fixture
def edr_alert_event_response(session_faker) -> tuple[dict[str, Any], TrellixResponse[EdrAlertAttributes]]:
    """
    Generate TrellixEdrResponse[EdrAlertAttributes].

    Args:
        session_faker: Faker

    Returns:
        TrellixResponse[EdrAlertAttributes]:
    """
    mocked_response = {
        "id": session_faker.uuid4(),
        "type": session_faker.word(),
        "attributes": {
            "Trace_Id": session_faker.uuid4(),
            "Parent_Trace_Id": session_faker.uuid4(),
            "Root_Trace_Id": session_faker.uuid4(),
            "DetectionDate": session_faker.date_time().isoformat(),
            "Event_Date": session_faker.date_time().isoformat(),
            "Activity": session_faker.word(),
            "Severity": session_faker.word(),
            "Score": 25,
            "Detection_Tags": [
                session_faker.word(),
                session_faker.word(),
                session_faker.word(),
            ],
            "Related_Trace_Id": [session_faker.uuid4()],
            "RuleId": session_faker.word(),
            "Rank": 25,
            "Pid": 6600,
            "Version": session_faker.word(),
            "Parents_Trace_Id": [session_faker.uuid4()],
            "ProcessName": "SDXHelper.exe",
            "User": {"domain": "CDA", "name": "cdaauto"},
            "CommandLine": '"C:\\Program Files\\Microsoft Office\\Root\\Office16\\SDXHelper.exe" -Embedding',
            "Hash_Id": "h7GhOs3Jm6Buj+LuzOOHBg==",
            "Host_OS": "windows",
            "Host_Name": "302W1022H264",
            "MAGUID": "ADB3C24C-232B-11EF-3D71-005056AC48D2",
            "Artifact": "Threat",
        },
    }

    return mocked_response, TrellixResponse[EdrAlertAttributes](
        **{**mocked_response, "attributes": EdrAlertAttributes.parse_response(mocked_response.get("attributes"))}
    )


@pytest.fixture
def edr_threat_event_response(session_faker) -> TrellixResponse[EdrThreatAttributes]:
    """
    Generate TrellixEdrResponse[EdrThreatAttributes].

    Args:
        session_faker: Faker

    Returns:
        TrellixResponse[EdrThreatAttributes]:
    """
    return TrellixResponse[EdrThreatAttributes](
        id=session_faker.uuid4(),
        type=session_faker.word(),
        attributes=EdrThreatAttributes(
            aggregationKey=session_faker.word(),
            severity=session_faker.word(),
            rank=session_faker.pyint(),
            score=session_faker.pyint(),
            name=session_faker.word(),
            type=session_faker.word(),
            status=session_faker.word(),
            firstDetected=session_faker.date_time().isoformat(),
            lastDetected=session_faker.date_time().isoformat(),
            hashes={session_faker.word(): session_faker.word(), session_faker.word(): session_faker.word()},
            interpreter={session_faker.word(): session_faker.pyint(), session_faker.word(): session_faker.word()},
        ),
    )


@pytest.fixture
def edr_detection_event_response(session_faker) -> TrellixResponse[EdrDetectionAttributes]:
    """
    Generate TrellixEdrResponse[EdrDetectionAttributes].

    Args:
        session_faker: Faker

    Returns:
        TrellixResponse[EdrDetectionAttributes]:
    """
    return TrellixResponse[EdrDetectionAttributes](
        type=session_faker.word(),
        attributes=EdrDetectionAttributes(
            traceId=session_faker.word(),
            firstDetected=session_faker.date_time().isoformat(),
            severity=session_faker.word(),
            rank=session_faker.pyint(),
            tags=[session_faker.word(), session_faker.word()],
            host={session_faker.word(): session_faker.word(), session_faker.word(): session_faker.word()},
            sha256=session_faker.word(),
        ),
    )


@pytest.fixture
def edr_affectedhost_event_response(session_faker) -> TrellixResponse[EdrAffectedhostAttributes]:
    """
    Generate TrellixEdrResponse[EdrAffectedhostAttributes].

    Args:
        session_faker: Faker

    Returns:
        TrellixResponse[EdrAffectedhostAttributes]:
    """
    return TrellixResponse[EdrAffectedhostAttributes](
        type=session_faker.word(),
        attributes=EdrAffectedhostAttributes(
            detectionsCount=session_faker.pyint(),
            severity=session_faker.word(),
            rank=session_faker.pyint(),
            firstDetected=session_faker.date_time().isoformat(),
            host={session_faker.word(): session_faker.word(), session_faker.word(): session_faker.pyint()},
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
