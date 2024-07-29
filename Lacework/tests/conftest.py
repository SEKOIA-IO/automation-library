import random
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from typing import Any, List

import pytest
from faker import Faker
from sekoia_automation import constants


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
    return random.randint(1, 10000)


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
def alerts_response(session_faker: Faker) -> dict[str, Any]:
    return {
        "paging": {
            "rows": 1000,
            "totalRows": 3120,
        },
        "data": [
            {
                "alertId": 855628,
                "startTime": "2022-06-30T00:00:00.000Z",
                "alertType": "MaliciousFile",
                "severity": "Critical",
                "internetExposure": "UnknownInternetExposure",
                "reachability": "UnknownReachability",
                "derivedFields": {"category": "Anomaly", "sub_category": "File", "source": "Agent"},
                "endTime": "2022-06-30T01:00:00.000Z",
                "lastUserUpdatedTime": "",
                "status": "Open",
                "alertName": "Clone of Cloud Activity log ingestion failure detected",
                "alertInfo": {
                    "subject": "Clone of Cloud Activity log ingestion failure detected: `azure-al-india-dnd` (and `3` more) is failing for data ingestion into Lacework",
                    "description": "New integration failure detected for azure-al-india-dnd (and 3 more)",
                },
                "policyId": "CUSTOM_PLATFORM_130",
            },
            {
                "alertId": 855629,
                "startTime": "2022-06-30T00:00:00.000Z",
                "alertType": "ChangedFile",
                "severity": "Critical",
                "internetExposure": "UnknownInternetExposure",
                "reachability": "UnknownReachability",
                "derivedFields": {"category": "Policy", "sub_category": "File", "source": "Agent"},
                "endTime": "2022-06-30T01:00:00.000Z",
                "lastUserUpdatedTime": "2022-06-30T01:26:51.392Z",
                "status": "Open",
                "alertName": "Unauthorized API Call",
                "alertInfo": {
                    "subject": "Unauthorized API Call: For account: `1234567890`: Unauthorized API call was attempted `4` times",
                    "description": "For account: 1234567890: Unauthorized API call was attempted 4 times by user  ABCD1234:Lacework",
                },
            },
        ],
    }


@pytest.fixture
def alerts_response_with_next(session_faker: Faker) -> dict[str, Any]:
    return {
        "paging": {
            "rows": 1000,
            "totalRows": 3120,
            "urls": {"nextPage": session_faker.uri()},
        },
        "data": [
            {
                "alertId": 855628,
                "startTime": "2022-07-30T00:00:00.000Z",
                "alertType": "MaliciousFile",
                "severity": "Critical",
                "internetExposure": "UnknownInternetExposure",
                "reachability": "UnknownReachability",
                "derivedFields": {"category": "Anomaly", "sub_category": "File", "source": "Agent"},
                "endTime": "2022-07-30T00:00:00.000Z",
                "lastUserUpdatedTime": "",
                "status": "Open",
                "alertName": "Clone of Cloud Activity log ingestion failure detected",
                "alertInfo": {
                    "subject": "Clone of Cloud Activity log ingestion failure detected: `azure-al-india-dnd` (and `3` more) is failing for data ingestion into Lacework",
                    "description": "New integration failure detected for azure-al-india-dnd (and 3 more)",
                },
                "policyId": "CUSTOM_PLATFORM_130",
            },
            {
                "alertId": 855629,
                "startTime": "2022-07-31T00:00:00.000Z",
                "alertType": "ChangedFile",
                "severity": "Critical",
                "internetExposure": "UnknownInternetExposure",
                "reachability": "UnknownReachability",
                "derivedFields": {"category": "Policy", "sub_category": "File", "source": "Agent"},
                "endTime": "2022-07-31T00:00:00.000Z",
                "lastUserUpdatedTime": "2022-06-30T01:26:51.392Z",
                "status": "Open",
                "alertName": "Unauthorized API Call",
                "alertInfo": {
                    "subject": "Unauthorized API Call: For account: `1234567890`: Unauthorized API call was attempted `4` times",
                    "description": "For account: 1234567890: Unauthorized API call was attempted 4 times by user  ABCD1234:Lacework",
                },
            },
        ],
    }


@pytest.fixture
def alerts_response_with_next_1(session_faker: Faker) -> dict[str, Any]:
    return {
        "paging": {
            "rows": 1000,
            "totalRows": 3120,
            "urls": {"nextPage": session_faker.uri()},
        },
        "data": [
            {
                "alertId": 855628,
                "startTime": "2022-08-30T00:00:00.000Z",
                "alertType": "MaliciousFile",
                "severity": "Critical",
                "internetExposure": "UnknownInternetExposure",
                "reachability": "UnknownReachability",
                "derivedFields": {"category": "Anomaly", "sub_category": "File", "source": "Agent"},
                "endTime": "2022-08-30T00:00:00.000Z",
                "lastUserUpdatedTime": "",
                "status": "Open",
                "alertName": "Clone of Cloud Activity log ingestion failure detected",
                "alertInfo": {
                    "subject": "Clone of Cloud Activity log ingestion failure detected: `azure-al-india-dnd` (and `3` more) is failing for data ingestion into Lacework",
                    "description": "New integration failure detected for azure-al-india-dnd (and 3 more)",
                },
                "policyId": "CUSTOM_PLATFORM_130",
            },
            {
                "alertId": 855629,
                "startTime": "2022-08-31T00:00:00.000Z",
                "alertType": "ChangedFile",
                "severity": "Critical",
                "internetExposure": "UnknownInternetExposure",
                "reachability": "UnknownReachability",
                "derivedFields": {"category": "Policy", "sub_category": "File", "source": "Agent"},
                "endTime": "2022-08-31T00:00:00.000Z",
                "lastUserUpdatedTime": "2022-06-30T01:26:51.392Z",
                "status": "Open",
                "alertName": "Unauthorized API Call",
                "alertInfo": {
                    "subject": "Unauthorized API Call: For account: `1234567890`: Unauthorized API call was attempted `4` times",
                    "description": "For account: 1234567890: Unauthorized API call was attempted 4 times by user  ABCD1234:Lacework",
                },
            },
        ],
    }


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage
