"""Contains tests for AuditLogConnector."""

from posixpath import join as urljoin
from typing import Any
from unittest.mock import MagicMock

import pytest
from aioresponses import aioresponses

from github_modules import GithubModule, GithubModuleConfiguration
from github_modules.audit_log_trigger import AuditLogConnector


@pytest.fixture
def intake_response(session_faker) -> dict[str, Any]:
    """
    Create intake response.

    Returns:
        dict[str, Any]:
    """
    return {"event_ids": [session_faker.word() for _ in range(10)]}


@pytest.fixture
def connector_with_api_key(symphony_storage, session_faker, intake_response):
    """
    Create a AuditLogConnector instance.

    Args:
        symphony_storage: str
        session_faker: Faker
        intake_response: list[str]
    """
    module = GithubModule()
    trigger = AuditLogConnector(module=module, data_path=symphony_storage)

    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.module.configuration = GithubModuleConfiguration(
        **{
            "apikey": session_faker.word(),
            "org_name": session_faker.word(),
        }
    )

    trigger.configuration = {
        "intake_server": "https://intake.sekoia.io",
        "intake_key": session_faker.word(),
    }

    yield trigger


@pytest.fixture
def connector_with_pem_file(symphony_storage, pem_content, session_faker, intake_response):
    """
    Create a AuditLogConnector instance.

    Args:
        symphony_storage: str
        pem_content: str
        session_faker: Faker
        intake_response: list[str]
    """
    module = GithubModule()
    trigger = AuditLogConnector(module=module, data_path=symphony_storage)

    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.module.configuration = GithubModuleConfiguration(
        **{
            "org_name": session_faker.word(),
            "pem_file": pem_content,
            "app_id": session_faker.pyint(),
        }
    )

    trigger.configuration = {
        "intake_server": "https://intake.sekoia.io",
        "intake_key": session_faker.word(),
    }

    yield trigger


@pytest.mark.asyncio
async def test_connector_get_github_client_instance(connector_with_api_key):
    """
    Test AuditLogConnector github_client.

    Args:
        connector_with_api_key: AuditLogConnector
    """
    assert AuditLogConnector._github_client is None

    github_client = connector_with_api_key.github_client

    assert connector_with_api_key._github_client == github_client
    assert connector_with_api_key.github_client == github_client


@pytest.mark.asyncio
async def test_next_batch_with_api_key(connector_with_api_key, github_response, intake_response):
    """
    Test AuditLogConnector next_batch.

    Args:
        connector_with_api_key: AuditLogConnector
        github_response: list[dict[str, Any]]
    """
    with aioresponses() as mocked_responses:
        audit_logs_url = (
            connector_with_api_key.github_client.audit_logs_url
            + "?order=asc&per_page=100&phrase=created%253A%253E{0}".format(connector_with_api_key.last_ts)
        )

        mocked_responses.get(
            audit_logs_url,
            status=200,
            payload=github_response,
        )

        mocked_responses.post(
            urljoin(connector_with_api_key.configuration.intake_server, "batch"),
            status=200,
            payload=intake_response,
        )

        await connector_with_api_key.next_batch()


@pytest.mark.asyncio
async def test_next_batch_with_pem_file(connector_with_pem_file, github_response, session_faker, intake_response):
    """
    Test AuditLogConnector next_batch.

    Args:
        connector_with_pem_file: AuditLogConnector
        github_response: list[dict[str, Any]]
    """
    with aioresponses() as mocked_responses:
        access_tokens_url = session_faker.uri()
        access_token = session_faker.word()
        mocked_responses.get(
            "https://api.github.com/orgs/{0}/installation".format(
                connector_with_pem_file.module.configuration.org_name,
            ),
            status=200,
            payload={"access_tokens_url": access_tokens_url},
        )

        mocked_responses.post(access_tokens_url, status=200, payload={"token": access_token})

        audit_logs_url = (
            connector_with_pem_file.github_client.audit_logs_url
            + "?order=asc&per_page=100&phrase=created%253A%253E{0}".format(connector_with_pem_file.last_ts)
        )

        mocked_responses.get(
            audit_logs_url,
            status=200,
            payload=github_response,
        )

        mocked_responses.post(
            urljoin(connector_with_pem_file.configuration.intake_server, "batch"),
            status=200,
            payload=intake_response,
        )

        await connector_with_pem_file.next_batch()
