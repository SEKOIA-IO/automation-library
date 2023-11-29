"""Tests related to CheckpointHarmonyConnector."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import pytest
from aioresponses import aioresponses
from faker import Faker

from client.token_refresher import CheckpointToken
from connectors import CheckpointModule
from connectors.checkpoint_harmony import CheckpointHarmonyConfiguration, CheckpointHarmonyConnector


@pytest.fixture
def checkpoint_harmony_connector(
    session_faker: Faker,
    symphony_storage: Path,
    checkpoint_module: CheckpointModule,
) -> CheckpointHarmonyConnector:
    """
    Create a CheckpointHarmonyConnector instance.

    Args:
        session_faker: Faker
        symphony_storage: Path
        checkpoint_module: CheckpointModule

    Returns:
        CheckpointHarmonyConnector:
    """
    configuration = CheckpointHarmonyConfiguration(
        intake_server=session_faker.url(),
        intake_key=session_faker.word(),
        ratelimit_per_minute=session_faker.random.randint(10, 100),
        chunk_size=session_faker.random.randint(100, 10000),
    )

    connector = CheckpointHarmonyConnector(module=checkpoint_module, data_path=symphony_storage)

    connector.configuration = configuration

    return connector


def create_event(session_faker: Faker, date: datetime) -> dict[str, Any]:
    """
    Create a CheckpointHarmony event.

    Args:
        session_faker:
        date:

    Returns:
        dict[str, Any]:
    """
    return {
        "id": session_faker.pyint(min_value=1, max_value=1000),
        "device_rooted": session_faker.pybool(),
        "attack_vector": session_faker.word(),
        "backend_last_updated": session_faker.word(),
        "details": session_faker.word(),
        "device_id": session_faker.word(),
        "email": session_faker.word(),
        "event": session_faker.word(),
        "event_timestamp": date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "mdm_uuid": session_faker.word(),
        "name": session_faker.word(),
        "number": session_faker.word(),
        "severity": session_faker.word(),
        "threat_factors": session_faker.word(),
        "device_model": session_faker.word(),
        "client_version": session_faker.word(),
    }


@pytest.mark.asyncio
async def test_checkpoint_harmony_connector_init_with_empty_client(
    session_faker: Faker,
    checkpoint_module: CheckpointModule,
):
    """
    Test CheckpointHarmonyConnector.

    Args:
        session_faker: Faker
        checkpoint_module: CheckpointModule
    """
    configuration = CheckpointHarmonyConfiguration(
        intake_server=session_faker.url(),
        intake_key=session_faker.word(),
        ratelimit_per_minute=session_faker.random.randint(10, 100),
        chunk_size=session_faker.random.randint(100, 10000),
    )

    connector = CheckpointHarmonyConnector()
    connector.module = checkpoint_module
    connector.configuration = configuration

    assert connector._checkpoint_client is None


@pytest.mark.asyncio
async def test_checkpoint_harmony_connector_last_event_date(
    checkpoint_harmony_connector: CheckpointHarmonyConnector,
):
    """
    Test CheckpointHarmonyConnector last_event_date.

    Args:
        checkpoint_harmony_connector: CheckpointHarmonyConnector
    """
    with checkpoint_harmony_connector.context as cache:
        cache["last_event_date"] = None

    current_date = datetime.now(timezone.utc).replace(microsecond=0)
    one_hour_ago = current_date - timedelta(hours=1)

    assert checkpoint_harmony_connector.last_event_date == one_hour_ago

    with checkpoint_harmony_connector.context as cache:
        cache["last_event_date"] = current_date.isoformat()

    assert checkpoint_harmony_connector.last_event_date == current_date

    with checkpoint_harmony_connector.context as cache:
        cache["last_event_date"] = (one_hour_ago - timedelta(minutes=20)).isoformat()

    assert checkpoint_harmony_connector.last_event_date == one_hour_ago


@pytest.mark.asyncio
async def test_checkpoint_harmony_connector_get_checkpoint_harmony_events(
    checkpoint_harmony_connector: CheckpointHarmonyConnector,
    http_token: tuple[CheckpointToken, dict[str, Any]],
    session_faker: Faker,
):
    """
    Test CheckpointHarmonyConnector get_checkpoint_harmony_events.

    Args:
        checkpoint_harmony_connector: CheckpointHarmonyConnector
        http_token: tuple[CheckpointToken, dict[str, Any]]
        session_faker: Faker
    """
    current_date = datetime.now(timezone.utc).replace(microsecond=0)
    half_hour_ago = current_date - timedelta(minutes=30)
    _, token_data = http_token

    with checkpoint_harmony_connector.context as cache:
        cache["last_event_date"] = half_hour_ago.isoformat()

    with aioresponses() as mocked:
        # Right now it is default value in limit count when we get events
        limit = 100

        base_url = checkpoint_harmony_connector.module.configuration.base_url
        auth_url = checkpoint_harmony_connector.module.configuration.authentication_url
        intake_post_url = urljoin(checkpoint_harmony_connector.configuration.intake_server, "/batch")
        half_hour_ago_str = half_hour_ago.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        get_events_url = urljoin(
            base_url,
            f"/app/SBM/external_api/v3/alert/?backend_last_updated__gte={half_hour_ago_str}&limit={limit}"
        )

        # all events except last one have event_timestamp < current date
        events = [
            create_event(
                session_faker, current_date - timedelta(minutes=session_faker.pyint(min_value=1, max_value=30))
            )
            for _ in range(session_faker.pyint(min_value=1, max_value=limit - 1))
        ]

        events.append(create_event(session_faker, current_date))

        events_data = {
            "meta": {
                "limit": limit,
                "next": session_faker.word(),
                "previous": session_faker.word(),
                "offset": 0,
                "total_count": 0,
            },
            "objects": events,
        }

        mocked.post(auth_url, status=200, payload=token_data)
        mocked.get(get_events_url, status=200, payload=events_data)
        mocked.post(
            intake_post_url,
            status=200,
            payload={"received": True, "event_ids": [session_faker.word() for _ in range(len(events))]},
        )

        result, resulted_event_date = await checkpoint_harmony_connector.get_checkpoint_harmony_events()

        assert len(result) == len(events)
        assert checkpoint_harmony_connector.last_event_date == current_date
        assert resulted_event_date == current_date.timestamp()
