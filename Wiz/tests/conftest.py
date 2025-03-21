"""Additional programmatic configuration for pytest."""

import asyncio
import time
from shutil import rmtree
from tempfile import mkdtemp
from typing import Any, List
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from sekoia_automation import constants

from wiz import WizModule, WizModuleConfig
from wiz.client.gql_client import WizGqlClient
from wiz.client.token_refresher import WizToken, WizTokenRefresher


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


@pytest.fixture(scope="session")
def http_token(session_faker) -> WizToken:
    """
    Generate WizToken.

    Args:
        session_faker: Faker

    Returns:
        HttpToken:
    """
    return WizToken(
        access_token=session_faker.word(),
        refresh_token=session_faker.word(),
        token_type=session_faker.word(),
        expires_in=5,  # in tests lets assume token expires in 5 seconds
        created_at=time.time(),
    )


@pytest.yield_fixture(scope="session")
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


@pytest.yield_fixture(scope="session")
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


@pytest.fixture(scope="session")
def auth_url(session_faker) -> str:
    return session_faker.uri()


@pytest.fixture(scope="session")
def tenant_url(session_faker) -> str:
    return session_faker.uri()


@pytest.fixture(scope="session")
def wiz_gql_client(session_faker, auth_url, tenant_url) -> WizGqlClient:
    client_id = session_faker.word()
    client_secret = session_faker.word()

    gql_client = WizGqlClient.create(client_id, client_secret, tenant_url)
    gql_client.token_refresher = WizTokenRefresher(client_id, client_secret, auth_url)

    return gql_client


@pytest.fixture(scope="session")
def module(symphony_storage, tenant_url, session_faker) -> WizModule:
    module = WizModule()
    module.configuration = WizModuleConfig(
        client_id=session_faker.word(),
        client_secret=session_faker.word(),
        tenant_url=tenant_url,
    )

    return module


@pytest.fixture
def audit_logs_response(session_faker: Faker) -> dict[str, dict[str, list[Any]]]:
    return {
        "auditLogEntries": {
            "nodes": [
                {
                    **session_faker.pydict(allowed_types=[str, int, float, bool]),
                    "timestamp": session_faker.date_time().isoformat(),
                    "id": session_faker.uuid4(),
                }
                for _ in range(10)
            ],
            "pageInfo": {
                "endCursor": session_faker.word(),
                "hasNextPage": False,
            },
        }
    }


@pytest.fixture
def audit_logs_response_with_next_page(session_faker: Faker) -> dict[str, dict[str, list[Any]]]:
    return {
        "auditLogEntries": {
            "nodes": [
                {
                    **session_faker.pydict(allowed_types=[str, int, float, bool]),
                    "timestamp": session_faker.date_time().isoformat(),
                    "id": session_faker.uuid4(),
                }
                for _ in range(10)
            ],
            "pageInfo": {
                "endCursor": session_faker.word(),
                "hasNextPage": True,
            },
        }
    }


@pytest.fixture
def alerts_response(session_faker: Faker) -> dict[str, dict[str, list[Any]]]:
    return {
        "issuesV2": {
            "nodes": [
                {
                    **session_faker.pydict(allowed_types=[str, int, float, bool]),
                    "createdAt": session_faker.date_time().isoformat(),
                    "id": session_faker.uuid4(),
                }
                for _ in range(10)
            ],
            "pageInfo": {
                "endCursor": session_faker.word(),
                "hasNextPage": False,
            },
        }
    }


@pytest.fixture
def alerts_response_with_next_page(session_faker: Faker) -> dict[str, dict[str, list[Any]]]:
    return {
        "issuesV2": {
            "nodes": [
                {
                    **session_faker.pydict(allowed_types=[str, int, float, bool]),
                    "createdAt": session_faker.date_time().isoformat(),
                    "id": session_faker.uuid4(),
                }
                for _ in range(10)
            ],
            "pageInfo": {
                "endCursor": session_faker.word(),
                "hasNextPage": True,
            },
        }
    }


@pytest.fixture
def cloud_configuration_findings_response(session_faker: Faker) -> dict[str, dict[str, list[Any]]]:
    return {
        "configurationFindings": {
            "nodes": [
                {
                    **session_faker.pydict(allowed_types=[str, int, float, bool]),
                    "analyzedAt": session_faker.date_time().isoformat(),
                    "id": session_faker.uuid4(),
                }
                for _ in range(10)
            ],
            "pageInfo": {
                "endCursor": session_faker.word(),
                "hasNextPage": False,
            },
        }
    }


@pytest.fixture
def cloud_configuration_findings_response_with_next_page(session_faker: Faker) -> dict[str, dict[str, list[Any]]]:
    return {
        "configurationFindings": {
            "nodes": [
                {
                    **session_faker.pydict(allowed_types=[str, int, float, bool]),
                    "analyzedAt": session_faker.date_time().isoformat(),
                    "id": session_faker.uuid4(),
                }
                for _ in range(10)
            ],
            "pageInfo": {
                "endCursor": session_faker.word(),
                "hasNextPage": True,
            },
        }
    }


@pytest.fixture
def vulnerability_findings_response(session_faker: Faker) -> dict[str, dict[str, list[Any]]]:
    return {
        "vulnerabilityFindings": {
            "nodes": [
                {
                    **session_faker.pydict(allowed_types=[str, int, float, bool]),
                    "firstDetectedAt": session_faker.date_time().isoformat(),
                    "id": session_faker.uuid4(),
                }
                for _ in range(10)
            ],
            "pageInfo": {
                "endCursor": session_faker.word(),
                "hasNextPage": False,
            },
        }
    }


@pytest.fixture
def vulnerability_findings_response_with_next_page(session_faker: Faker) -> dict[str, dict[str, list[Any]]]:
    return {
        "vulnerabilityFindings": {
            "nodes": [
                {
                    **session_faker.pydict(allowed_types=[str, int, float, bool]),
                    "firstDetectedAt": session_faker.date_time().isoformat(),
                    "id": session_faker.uuid4(),
                }
                for _ in range(10)
            ],
            "pageInfo": {
                "endCursor": session_faker.word(),
                "hasNextPage": True,
            },
        }
    }


@pytest.fixture(scope="session")
def mock_push_data_to_intakes() -> AsyncMock:
    """
    Mocked push_data_to_intakes method.

    Returns:
        AsyncMock:
    """

    def side_effect_return_input(events: list[str]) -> list[str]:
        """
        Return input value.

        Uses in side_effect to return input value from mocked function.

        Args:
            events: list[str]

        Returns:
            list[str]:
        """
        return events

    return AsyncMock(side_effect=side_effect_return_input)
