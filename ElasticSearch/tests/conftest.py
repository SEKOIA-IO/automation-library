"""Additional programmatic configuration for pytest."""

import asyncio
import time
from shutil import rmtree
from tempfile import mkdtemp
from typing import Any, Generator, List
from unittest.mock import AsyncMock

import pytest
from faker import Faker
from sekoia_automation import constants

from elasticsearch_module import ElasticSearchConfiguration, ElasticSearchModule
from elasticsearch_module.client import ElasticSearchClient


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
def elasticsearch_error_response() -> dict[str, Any]:
    return {
        "error": {
            "root_cause": [
                {
                    "type": "index_not_found_exception",
                    "reason": "no such index [my-index]",
                    "resource.type": "index_or_alias",
                    "resource.id": "my-index",
                    "index_uuid": "_na_",
                    "index": "my-index",
                }
            ],
            "type": "index_not_found_exception",
            "reason": "no such index [my-index]",
            "resource.type": "index_or_alias",
            "resource.id": "my-index",
            "index_uuid": "_na_",
            "index": "my-index",
        },
        "status": 404,
    }


@pytest.fixture(scope="session")
def elasticsearch_response_finished() -> dict[str, Any]:
    return {
        "is_running": False,
        "took": 9,
        "is_partial": False,
        "all_columns": [{"name": "text", "type": "text"}, {"name": "text.keyword", "type": "keyword"}],
        "columns": [{"name": "text", "type": "text"}],
        "values": [
            ["Random text 1"],
            ["Random text 2"],
            ["Random text 3"],
            ["Random text 4"],
        ],
    }


@pytest.fixture(scope="session")
def elasticsearch_response_query_id() -> dict[str, Any]:
    return {"id": "random_query_id"}


@pytest.yield_fixture(scope="session")
def symphony_storage() -> Generator[str, Any, None]:
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
def elasticsearch_url(session_faker) -> str:
    return session_faker.url()


@pytest.fixture(scope="session")
def api_key(session_faker) -> str:
    return session_faker.word()


@pytest.fixture(scope="session")
def module(symphony_storage, elasticsearch_url, api_key) -> ElasticSearchModule:
    module = ElasticSearchModule()
    module.configuration = {
        "url": elasticsearch_url,
        "api_key": api_key,
        "disable_certificate_verification": True,
        "sha256_tls_fingerprint": None,
    }

    return module


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
