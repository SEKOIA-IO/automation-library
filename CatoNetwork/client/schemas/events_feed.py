"""Schemas for the events feed."""

from enum import Enum
from typing import Any

from gql import gql
from pydantic import BaseModel


class EventsFeedQueries(Enum):
    """EventsFeedQueries."""

    GET_EVENTS_FEED = gql(
        """
            query($accountIds: [ID!], $lastEventId: String) {
                eventsFeed(accountIDs: $accountIds, marker: $lastEventId) {
                    marker
                    fetchedCount
                    accounts {
                        records {
                            time
                            fieldsMap
                       }
                    }
                  }
            }
        """
    )


class EventsFeedRecordSchema(BaseModel):
    """EventsFeedRecordSchema."""

    time: str
    fieldsMap: dict[str, Any]


class EventsFeedAccountsSchema(BaseModel):
    """EventsFeedAccountsSchema."""

    records: list[EventsFeedRecordSchema]


class EventsFeedResponseSchema(BaseModel):
    """EventsFeedResponseSchema is based on `EventsFeedQueries.GET_EVENTS_FEED` query."""

    marker: str
    fetchedCount: int
    accounts: list[EventsFeedAccountsSchema]
