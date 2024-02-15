"""Tests for events feed schemas."""

from typing import Any

import pytest
from faker import Faker

from client.schemas.events_feed import EventsFeedResponseSchema


@pytest.fixture
def mock_events_feed_response(session_faker: Faker) -> dict[str, Any]:
    """
    Mock EventsFeedResponseSchema.

    Args:
        session_faker: Faker

    Returns:
        dict[str, Any]:
    """
    # You can use the faker data to create a mock response for the API
    fake_marker = session_faker.uuid4()
    fake_fetched_count = session_faker.random_int(min=1, max=100)
    fake_time = session_faker.date_time().isoformat()
    fake_fields_map = {
        "field1": session_faker.word(),
        "field2": session_faker.random_int(min=1, max=100),
    }

    return {
        "marker": fake_marker,
        "fetchedCount": fake_fetched_count,
        "accounts": [
            {
                "records": [
                    {
                        "time": fake_time,
                        "fieldsMap": fake_fields_map,
                    }
                ]
            }
        ],
    }


@pytest.mark.asyncio
async def test_events_feed_response_schema(mock_events_feed_response):
    """
    Test EventsFeedResponseSchema.

    Args:
        mock_events_feed_response:
    """
    # Test EventsFeedResponseSchema using the mock response
    response = EventsFeedResponseSchema.parse_obj(mock_events_feed_response)

    assert response.marker == mock_events_feed_response["marker"]
    assert response.fetchedCount == mock_events_feed_response["fetchedCount"]
    assert len(response.accounts) == 1
    assert len(response.accounts[0].records) == 1
    assert response.accounts[0].records[0].time == mock_events_feed_response["accounts"][0]["records"][0]["time"]
    assert (
        response.accounts[0].records[0].fieldsMap
        == mock_events_feed_response["accounts"][0]["records"][0]["fieldsMap"]
    )
