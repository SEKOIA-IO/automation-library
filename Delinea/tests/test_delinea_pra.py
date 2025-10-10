from datetime import datetime
from unittest.mock import Mock

import pytest
from aioresponses import aioresponses
from freezegun import freeze_time

from delinea.delinea_pra import DelineaPraConnector, DelineaPraConnectorConfig


@pytest.fixture
def delinea_pra(symphony_storage, delinea_module, mock_push_data_to_intakes) -> DelineaPraConnector:
    connector = DelineaPraConnector(data_path=symphony_storage)
    connector.module = delinea_module
    connector.configuration = DelineaPraConnectorConfig(
        **{
            "chunk_size": 3,
            "intake_key": "",
        }
    )

    connector.push_data_to_intakes = mock_push_data_to_intakes
    connector.log_exception = Mock()
    connector.log = Mock()

    return connector


@freeze_time("2023-01-01T00:30:00")
@pytest.mark.asyncio
async def test_delinea_pra_connector_1(delinea_pra: DelineaPraConnector) -> None:
    """
    Test DelineaPraConnector.

    Args:
        delinea_pra: DelineaPraConnector
    """
    with aioresponses() as m:
        # mock auth token
        m.post(
            f"{delinea_pra.client.base_url}/identity/api/oauth2/token/xpmplatform",
            payload={
                "access_token": "test_token",
                "expires_in": 3600,
            },
            repeat=True,
        )

        # mock events with multipage result
        delinea_pra.events_cache["randomId1"] = True  # simulate that first event is already in cache

        first_result = {
            "auditEvents": [
                # '%Y-%m-%dT%H:%M:%S.%fZ format
                {"eventMessageId": "randomId1", "eventDateTime": "2025-09-18T13:34:17.603+00:00"},
                {"eventMessageId": "randomId2", "eventDateTime": "2023-01-02T00:30:00.0+00:00"},
            ],
        }
        first_url = delinea_pra.client.get_audit_events_url(
            start_date=delinea_pra.last_event_date.offset, page=1, end_date=datetime.now()
        )
        m.get(first_url, payload=first_result)

        second_result = {
            "auditEvents": [
                {"eventMessageId": "randomId3", "eventDateTime": "2023-01-03T00:30:00.0+00:00"},
                {"eventMessageId": "randomId4", "eventDateTime": "2023-01-03T00:30:00.0+00:00"},
                {"eventMessageId": "randomId5", "eventDateTime": "2023-01-03T00:30:00.0+00:00"},
            ],
        }
        second_url = delinea_pra.client.get_audit_events_url(
            start_date=delinea_pra.last_event_date.offset, page=2, end_date=datetime.now()
        )
        m.get(second_url, payload=second_result)

        third_result = {
            "auditEvents": [],
        }
        third_url = delinea_pra.client.get_audit_events_url(
            start_date=delinea_pra.last_event_date.offset, page=3, end_date=datetime.now()
        )
        m.get(third_url, payload=third_result)

        results = await delinea_pra.get_events()
        assert results == 4  # first event should be in cache

        await delinea_pra.client.close()
