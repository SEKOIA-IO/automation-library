from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator, Any
from urllib.parse import urljoin

from aiolimiter import AsyncLimiter
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

from wiz.client.token_refresher import WizTokenRefresher


class WizGqlClient(object):
    _rate_limiter: AsyncLimiter | None = None

    def __init__(
            self,
            client_id: str,
            client_secret: str,
            tenant_url: str,
            token_refresher: WizTokenRefresher,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_url = tenant_url
        self.token_refresher = token_refresher

    @classmethod
    def create(cls, client_id: str, client_secret: str, tenant_url: str) -> "WizGqlClient":
        auth_url = WizTokenRefresher.create_url_from_tenant(tenant_url)
        token_refresher = WizTokenRefresher(client_id, client_secret, auth_url)

        return cls(client_id, client_secret, tenant_url, token_refresher)

    async def close(self) -> None:
        if self.token_refresher is not None:
            await self.token_refresher.close()

        self._rate_limiter = None

    @asynccontextmanager
    async def _session(self) -> AsyncGenerator[Client, None]:
        if self._rate_limiter is None:
            self._rate_limiter = AsyncLimiter(max_rate=3, time_period=1)  # 3 requests per second as per docs

        async with self._rate_limiter:
            async with self.token_refresher.with_access_token() as token:
                transport = AIOHTTPTransport(
                    url=urljoin(self.tenant_url, "graphql"),
                    headers={"Authorization": f"Bearer {token.access_token}"},
                )

                yield Client(transport=transport)

    async def request(self, query: str, variable_values: dict[str, str] | None = None) -> dict[str, str]:
        async with self._session() as session:
            result: dict[str, str] = await session.execute_async(gql(query), variable_values=variable_values)

            return result

    async def get_alerts(self, start_date: datetime, after: str | None = None ) -> tuple[
        list[dict[str, Any]], str | None]:
        query = """
            query ListIssues($after: String, $startDateTime: DateTime, $limit: Int = 100) {
              issuesV2(
                filterBy: {
                    status: [OPEN, IN_PROGRESS],
                    createdAt: {after: $startDateTime}
                }
                first: $limit
                after: $after
                orderBy: {
                    field: CREATED_AT,
                    direction: ASC
                }
              ) {
                nodes {
                  id
                  sourceRule {
                    __typename
                    ... on Control {
                      id
                      name
                      controlDescription: description
                      resolutionRecommendation
                      securitySubCategories {
                        title
                        category {
                          name
                        }
                      }
                      risks
                    }
                    ... on CloudEventRule {
                      id
                      name
                      cloudEventRuleDescription: description
                      sourceType
                      type
                      risks
                      securitySubCategories {
                        title
                        category {
                          name
                        }
                      }
                    }
                    ... on CloudConfigurationRule {
                      id
                      name
                      cloudConfigurationRuleDescription: description
                      remediationInstructions
                      serviceType
                      risks
                      securitySubCategories {
                        title
                        category {
                          name
                        }
                      }
                    }
                  }
                  createdAt
                  updatedAt
                  dueAt
                  type
                  resolvedAt
                  statusChangedAt
                  status
                  severity
                  entitySnapshot {
                    id
                    type
                    nativeType
                    name
                    status
                    cloudPlatform
                    cloudProviderURL
                    providerId
                    region
                  }
                }
                pageInfo {
                  hasNextPage
                  endCursor
                }
              }
            }
        """

        variable_values = {
            "after": after,
            "startDateTime": start_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        }

        response = await self.request(query, variable_values=variable_values)

        result = response.get('issuesV2', {}).get('nodes', [])
        end_cursor = response.get('issuesV2', {}).get('pageInfo', {}).get('endCursor')
        has_next_page = response.get('issuesV2', {}).get('pageInfo', {}).get('hasNextPage')

        if has_next_page:
            return result, end_cursor

        return result, None
