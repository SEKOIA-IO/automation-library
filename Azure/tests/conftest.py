"""Additional programmatic configuration for pytest."""

import asyncio
import random
from datetime import datetime
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from typing import List

import orjson
import pytest
from faker import Faker
from sekoia_automation import constants


@pytest.fixture
def symphony_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()

    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


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
def container_name(session_faker) -> str:
    """
    Generate random container_name.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.word()


@pytest.fixture
def account_name(session_faker) -> str:
    """
    Generate random account_name.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.word() + session_faker.word()


@pytest.fixture
def account_key(session_faker) -> str:
    """
    Generate random account_key.

    Args:
        session_faker: Faker

    Returns:
        str:
    """
    return session_faker.word() + session_faker.word() + session_faker.word()


@pytest.fixture
def blob_content(session_faker) -> bytes:
    result = {
        "records": [
            {
                "time": datetime.now().isoformat(),
                "systemId": "systemId",
                "macAddress": "123123123",
                "category": "Category",
                "resourceId": "resourceId",
                "operationName": "NetworkSecurityGroupFlowEvents",
                "properties": {
                    "Version": 2,
                    "flows": [
                        {
                            "rule": "DefaultRule_AllowInternetOutBound",
                            "flows": [
                                {
                                    "mac": "123123",
                                    "flowTuples": [
                                        "1695023147,1.2.3.4,5.6.7.8,123,123,U,O,A,B,,,,",
                                    ],
                                }
                            ],
                        },
                        {
                            "rule": "DefaultRule_DenyAllInBound",
                            "flows": [
                                {
                                    "mac": "123123",
                                    "flowTuples": [
                                        "1695023164,1.2.3.4,5.6.7.8,123,123,T,I,D,B,,,,",
                                    ],
                                }
                            ],
                        },
                    ],
                },
            }
        ]
    }

    return orjson.dumps(result)


@pytest.fixture
def blob_content_simple_format(session_faker) -> bytes:
    result = orjson.dumps(
        {
            "time": datetime.now().isoformat(),
            "systemId": "systemId",
            "macAddress": "123123123",
            "category": "Category",
            "resourceId": "resourceId",
            "operationName": "NetworkSecurityGroupFlowEvents",
            "properties": {
                "Version": 2,
                "flows": [
                    {
                        "rule": "DefaultRule_AllowInternetOutBound",
                        "flows": [
                            {
                                "mac": "123123",
                                "flowTuples": [
                                    "1695023147,1.2.3.4,5.6.7.8,123,123,U,O,A,B,,,,",
                                ],
                            }
                        ],
                    },
                    {
                        "rule": "DefaultRule_DenyAllInBound",
                        "flows": [
                            {
                                "mac": "123123",
                                "flowTuples": [
                                    "1695023164,1.2.3.4,5.6.7.8,123,123,T,I,D,B,,,,",
                                ],
                            }
                        ],
                    },
                ],
            },
        }
    ).decode("utf-8")

    return "\n".join([result, result]).encode("utf-8")


@pytest.fixture(scope="session")
def event_loop():
    """
    Create event loop for pytest.mark.asyncio.

    Yields:
        loop:
    """
    loop = asyncio.get_event_loop()

    yield loop

    loop.close()
