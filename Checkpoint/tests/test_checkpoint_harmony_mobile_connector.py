"""Tests related to CheckpointHarmonyConnector."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from posixpath import join as urljoin
from typing import Any

import pytest
from aioresponses import aioresponses
from faker import Faker

from connectors import CheckpointModule
from connectors.checkpoint_harmony_mobile import CheckpointHarmonyMobileConfiguration, CheckpointHarmonyMobileConnector
from connectors.client.token_refresher import CheckpointToken


@pytest.fixture
def checkpoint_harmony_connector(
    session_faker: Faker,
    symphony_storage: Path,
    checkpoint_module: CheckpointModule,
) -> CheckpointHarmonyMobileConnector:
    """
    Create a CheckpointHarmonyMobileConnector instance.

    Args:
        session_faker: Faker
        symphony_storage: Path
        checkpoint_module: CheckpointModule

    Returns:
        CheckpointHarmonyConnector:
    """
    configuration = CheckpointHarmonyMobileConfiguration(
        intake_server=session_faker.url(),
        intake_key=session_faker.word(),
        ratelimit_per_minute=session_faker.random.randint(10, 100),
        chunk_size=session_faker.random.randint(100, 10000),
    )

    connector = CheckpointHarmonyMobileConnector(module=checkpoint_module, data_path=symphony_storage)

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
        "backend_last_updated": date.strftime("%m/%d/%Y %H:%M:%S"),
        "details": session_faker.word(),
        "device_id": session_faker.word(),
        "email": session_faker.word(),
        "event": session_faker.word(),
        "event_timestamp": date.strftime("%m/%d/%Y %H:%M:%S"),
        "mdm_uuid": session_faker.word(),
        "name": session_faker.word(),
        "number": session_faker.word(),
        "severity": session_faker.word(),
        "threat_factors": session_faker.word(),
        "device_model": session_faker.word(),
        "client_version": session_faker.word(),
    }


@pytest.mark.asyncio
async def test_checkpoint_harmony_connector_get_checkpoint_harmony_events(
    checkpoint_harmony_connector: CheckpointHarmonyMobileConnector,
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

        base_url = urljoin(checkpoint_harmony_connector.module.configuration.base_url, "app/SBM")
        auth_url = checkpoint_harmony_connector.module.configuration.authentication_url
        intake_post_url = urljoin(checkpoint_harmony_connector.configuration.intake_server, "batch")

        time_events_from = half_hour_ago + timedelta(seconds=1)
        time_events_to = time_events_from + timedelta(minutes=1)
        time_events_from_str = time_events_from.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        time_events_to_str = time_events_to.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        endpoints = [
            f"/external_api/v3/alert/?backend_last_updated__gte={time_events_from_str}&backend_last_updated__lte={time_events_to_str}&limit={limit}",
            f"/external_api/v3/alert/?backend_last_updated__gte={time_events_from_str}&backend_last_updated__lte={time_events_to_str}&limit={limit}&offset={limit}",
            f"/external_api/v3/alert/?backend_last_updated__gte={time_events_from_str}&backend_last_updated__lte={time_events_to_str}&limit={limit}&offset={limit*2}",
        ]

        events = []
        for index, endpoint in enumerate(endpoints):
            # all events except last one have event_timestamp < current date
            objects = [
                create_event(
                    session_faker, current_date - timedelta(minutes=session_faker.pyint(min_value=1, max_value=30))
                )
                for _ in range(session_faker.pyint(min_value=1, max_value=limit - 1))
            ]

            objects.append(create_event(session_faker, current_date))
            events.extend(objects)

            events_data = {
                "meta": {
                    "limit": limit,
                    "next": endpoints[index + 1] if index + 1 < len(endpoints) else None,
                    "previous": session_faker.word(),
                    "offset": 0,
                    "total_count": 0,
                },
                "objects": objects,
            }
            mocked.get(f"{base_url}{endpoint}", status=200, payload=events_data)

        mocked.post(auth_url, status=200, payload=token_data)
        mocked.post(
            intake_post_url,
            status=200,
            payload={"received": True, "event_ids": [session_faker.word() for _ in range(len(events))]},
        )

        result = await checkpoint_harmony_connector.fetch_checkpoint_harmony_events(
            time_events_from, time_events_to, limit
        )

        assert len(result) == len(events)
        await checkpoint_harmony_connector.checkpoint_client.close()
