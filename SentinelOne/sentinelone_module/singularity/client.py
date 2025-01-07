import logging
import os
from contextlib import asynccontextmanager
from posixpath import join as urljoin
from typing import Any, AsyncGenerator

import orjson
from aiolimiter import AsyncLimiter
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportServerError
from gql.transport.requests import log as requests_logger
from graphql import ExecutionResult
from pydantic import BaseModel

requests_logger.setLevel(int(os.getenv("GQL_LOG_LEVEL", logging.WARNING)))  # Warning level by default


class ListAlertsResult(BaseModel):
    total_count: int
    end_cursor: str | None
    has_next_page: bool
    alerts: list[dict[str, Any]]


class SentinelOneAPIErrors(Exception):
    @classmethod
    def from_response(cls, response: dict[str, Any]) -> "SentinelOneAPIErrors":
        return cls(orjson.dumps(response["errors"]).decode("utf-8"))


class SentinelOneServerError(SentinelOneAPIErrors):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class SingularityClient(object):
    _client: Client | None = None
    _rate_limiter: AsyncLimiter | None = None

    def __init__(self, api_token: str, hostname: str) -> None:
        self.api_token = api_token
        self.hostname = hostname

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close_async()
            self._client = None

        self._rate_limiter = None

    @asynccontextmanager
    async def _session(self) -> AsyncGenerator[Client, None]:
        if self._client is None:
            transport = AIOHTTPTransport(
                url=urljoin(f"https://{self.hostname}", "web/api/v2.1/unifiedalerts/graphql"),
                headers={"Authorization": f"Bearer {self.api_token}"},
            )

            self._client = Client(transport=transport)

        if self._rate_limiter is None:
            self._rate_limiter = AsyncLimiter(max_rate=25, time_period=1)  # 25 requests per second

        async with self._rate_limiter:
            yield self._client

    async def query(self, query: str, variable_values: dict[str, Any] | None = None) -> dict[str, Any]:
        async with self._session() as session:
            try:
                result: dict[str, Any] = await session.execute_async(gql(query), variable_values=variable_values)
            except TransportServerError as e:
                if e.code == 401:
                    raise SentinelOneServerError(f"Status code {e.code}. Authentication failed") from e

                if e.code == 403:
                    raise SentinelOneServerError(f"Status code {e.code}. Permission denied") from e

                raise e

            return result

    async def get_alert_details(self, alert_id: str) -> dict[str, Any] | None:
        query = """
            query alert($id: ID!) {
                alert(id: $id) {
                  analystVerdict
                  analytics {
                    category
                  }
                  asset {
                    agentUuid
                    agentVersion
                    category
                    name
                    osType
                    osVersion
                    type
                    subcategory
                  }
                  rawData
                }
            }
        """

        variables = {"id": alert_id}

        response = await self.query(query, variable_values=variables)

        if response.get("errors") is not None:
            raise SentinelOneAPIErrors.from_response(response)

        return response.get("alert")

    async def list_alerts(
        self, product_name: str, after: str | None = None, start_time: int | None = None
    ) -> ListAlertsResult:
        query = """
            query listAlerts($productName: String!, $after: String, $startDateTime: Long) {
                alerts(
                        after: $after,
                        filters: [
                          {fieldId: "detectionProduct", stringEqual: { value: $productName }}
                          {fieldId: "detectedAt", dateTimeRange: { start: $startDateTime, startInclusive: true }}
                        ]
                        sort: {by: "detectedAt", order: ASC}
                ) {
                    edges {
                        node {
                            id
                            name
                            description
                            detectedAt
                            attackSurfaces
                            detectionSource{
                                product
                            }
                            name
                            status
                            assignee {
                                fullName
                            }
                            classification
                            confidenceLevel
                            firstSeenAt
                            lastSeenAt
                            process {
                              cmdLine
                              file {
                                path
                                sha1
                                sha256
                                md5
                              }
                              parentName
                            }
                            result
                            storylineId
                        }
                    },
                  pageInfo {
                      endCursor
                      hasNextPage
                  }
                  totalCount
                }
            }
        """

        variables = {"productName": product_name, "after": after, "startDateTime": start_time}

        response = await self.query(query, variable_values=variables)

        if response.get("errors") is not None:
            raise SentinelOneAPIErrors.from_response(response)

        return ListAlertsResult(
            total_count=response["alerts"]["totalCount"],
            end_cursor=response["alerts"]["pageInfo"]["endCursor"],
            has_next_page=response["alerts"]["pageInfo"]["hasNextPage"],
            alerts=[edge["node"] for edge in response["alerts"]["edges"]],
        )
