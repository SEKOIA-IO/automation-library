from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator
from urllib.parse import urljoin

import orjson
from aiolimiter import AsyncLimiter
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError, TransportServerError
from pydantic import BaseModel

from wiz.client.token_refresher import WizTokenRefresher


class WizResult(BaseModel):
    end_cursor: str | None
    has_next_page: bool
    result: list[dict[str, Any]]

    @classmethod
    def from_audit_logs_response(cls, response: dict[str, Any]) -> "WizResult":
        return cls(
            end_cursor=response.get("auditLogEntries", {}).get("pageInfo", {}).get("endCursor"),
            has_next_page=response.get("auditLogEntries", {}).get("pageInfo", {}).get("hasNextPage", False),
            result=response.get("auditLogEntries", {}).get("nodes", []),
        )

    @classmethod
    def from_alerts_response(cls, response: dict[str, Any]) -> "WizResult":
        return cls(
            end_cursor=response.get("issuesV2", {}).get("pageInfo", {}).get("endCursor"),
            has_next_page=response.get("issuesV2", {}).get("pageInfo", {}).get("hasNextPage", False),
            result=response.get("issuesV2", {}).get("nodes", []),
        )

    @classmethod
    def from_cloud_configuration_findings_response(cls, response: dict[str, Any]) -> "WizResult":
        return cls(
            end_cursor=response.get("configurationFindings", {}).get("pageInfo", {}).get("endCursor"),
            has_next_page=response.get("configurationFindings", {}).get("pageInfo", {}).get("hasNextPage", False),
            result=response.get("configurationFindings", {}).get("nodes", []),
        )

    @classmethod
    def from_vulnerability_findings_response(cls, response: dict[str, Any]) -> "WizResult":
        return cls(
            end_cursor=response.get("vulnerabilityFindings", {}).get("pageInfo", {}).get("endCursor"),
            has_next_page=response.get("vulnerabilityFindings", {}).get("pageInfo", {}).get("hasNextPage", False),
            result=response.get("vulnerabilityFindings", {}).get("nodes", []),
        )


class WizErrors(Exception):

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message)
        self.message = message

    @classmethod
    def from_response(cls, response: dict[str, Any]) -> "WizErrors":
        return cls(orjson.dumps(response["errors"]).decode("utf-8"))

    @classmethod
    def from_error(cls, query_error: TransportQueryError) -> "WizErrors":
        return cls(orjson.dumps(query_error.errors).decode("utf-8"))


class WizServerError(WizErrors):
    """WizServerError"""


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

    async def request(self, query: str, variable_values: dict[str, str | None] | None = None) -> dict[str, Any]:
        async with self._session() as session:
            try:
                result: dict[str, Any] = await session.execute_async(gql(query), variable_values=variable_values)

            except TransportServerError as e:
                if e.code == 401:
                    raise WizServerError(f"Status code {e.code}. Authentication failed") from e

                if e.code == 403:
                    raise WizServerError(f"Status code {e.code}. Permission denied") from e

                raise WizErrors from e

            except TransportQueryError as e:
                if e.errors:
                    raise WizErrors.from_error(e) from e

                raise e

            return result

    async def get_audit_logs(self, start_date: datetime, after: str | None = None) -> WizResult:
        query = """
            query AuditLogTable($after: String, $startDateTime: DateTime, $limit: Int = 100) {
                auditLogEntries(
                    first: $limit,
                    after: $after,
                    filterBy: {
                        timestamp: { 
                            after: $startDateTime
                        }
                    }
                ) {
                  nodes {
                    id
                    action
                    requestId
                    status
                    timestamp
                    actionParameters
                    userAgent
                    sourceIP
                    serviceAccount {
                      id
                      name
                    }
                    user {
                      id
                      name
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

        if response.get("errors") is not None:
            raise WizErrors.from_response(response)

        return WizResult.from_audit_logs_response(response)

    async def get_alerts(self, start_date: datetime, after: str | None = None) -> WizResult:
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

        if response.get("errors") is not None:
            raise WizErrors.from_response(response)

        return WizResult.from_alerts_response(response)

    async def get_cloud_configuration_findings(self, start_date: datetime, after: str | None = None) -> WizResult:
        query = """
              query ListCloudConfigurationFindings(
                $after: String,
                $startDateTime: DateTime
                $limit: Int = 100
              ) {
                configurationFindings(
                  first: $limit
                  after: $after
                  filterBy: {
                    analyzedAt: {after: $startDateTime}
                  }
                  orderBy: {
                    field: FIRST_SEEN_AT,
                    direction: ASC
                  }
                ) {
                  nodes {
                    id
                    targetExternalId
                    deleted
                    targetObjectProviderUniqueId
                    firstSeenAt
                    analyzedAt
                    severity
                    result
                    status
                    remediation
                    resource {
                      id
                      providerId
                      name
                      nativeType
                      type
                      region
                      subscription {
                        id
                        name
                        externalId
                        cloudProvider
                      }
                      projects {
                        id
                        name
                        riskProfile {
                          businessImpact
                        }
                      }
                      tags {
                        key
                        value
                      }
                    }
                    rule {
                      id
                      graphId
                      name
                      description
                      remediationInstructions
                      functionAsControl
                    }
                    securitySubCategories {
                      id
                      title
                      category {
                        id
                        name
                        framework {
                          id
                          name
                        }
                      }
                    }
                    ignoreRules{
                      id
                      name
                      enabled
                      expiredAt
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

        if response.get("errors") is not None:
            raise WizErrors.from_response(response)

        return WizResult.from_cloud_configuration_findings_response(response)

    async def get_vulnerability_findings(self, start_date: datetime, after: str | None = None) -> WizResult:
        query = """
            query ListVulnerabilityFindings(
                $after: String,
                $startDateTime: DateTime
                $limit: Int = 100
            ) {
                vulnerabilityFindings(
                  first: $limit
                  after: $after
                  filterBy: {
                    firstSeenAt: {after: $startDateTime}
                  }
                ) {
                  nodes {
                    id
                    portalUrl
                    name
                    CVEDescription
                    CVSSSeverity
                    score
                    exploitabilityScore
                    severity
                    nvdSeverity
                    weightedSeverity
                    impactScore
                    dataSourceName
                    hasExploit
                    hasCisaKevExploit
                    status
                    vendorSeverity
                    firstDetectedAt
                    lastDetectedAt
                    resolvedAt
                    description
                    remediation
                    detailedName
                    version
                    fixedVersion
                    detectionMethod
                    link
                    locationPath
                    resolutionReason
                    epssSeverity
                    epssPercentile
                    epssProbability
                    validatedInRuntime
                    layerMetadata {
                      id
                      details
                      isBaseLayer
                    }
                    projects {
                      id
                      name
                      slug
                      businessUnit
                      riskProfile {
                        businessImpact
                      }
                    }
                    ignoreRules {
                      id
                      name
                      enabled
                      expiredAt
                    }
                    cvssv2 {
                      attackVector
                      attackComplexity
                      confidentialityImpact
                      integrityImpact
                      privilegesRequired
                      userInteractionRequired
                    }
                    cvssv3 {
                      attackVector
                      attackComplexity
                      confidentialityImpact
                      integrityImpact
                      privilegesRequired
                      userInteractionRequired
                    }
                    relatedIssueAnalytics {
                      issueCount
                      criticalSeverityCount
                      highSeverityCount
                      mediumSeverityCount
                      lowSeverityCount
                      informationalSeverityCount
                    }
                    cnaScore
                    vulnerableAsset {
                      ... on VulnerableAssetBase {
                        id
                        type
                        name
                        region
                        providerUniqueId
                        cloudProviderURL
                        cloudPlatform
                        status
                        subscriptionName
                        subscriptionExternalId
                        subscriptionId
                        tags
                        hasLimitedInternetExposure
                        hasWideInternetExposure
                        isAccessibleFromVPN
                        isAccessibleFromOtherVnets
                        isAccessibleFromOtherSubscriptions
                      }
                      ... on VulnerableAssetVirtualMachine {
                        operatingSystem
                        ipAddresses
                        imageName
                        nativeType
                        computeInstanceGroup {
                          id
                          externalId
                          name
                          replicaCount
                          tags
                        }
                      }
                      ... on VulnerableAssetServerless {
                        runtime
                      }
                      ... on VulnerableAssetContainerImage {
                        imageId
                        scanSource
                        registry {
                          name
                          externalId
                        }
                        repository {
                          name
                          externalId
                        }
                        executionControllers {
                          id
                          name
                          entityType
                          externalId
                          providerUniqueId
                          name
                          subscriptionExternalId
                          subscriptionId
                          subscriptionName
                          ancestors {
                            id
                            name
                            entityType
                            externalId
                            providerUniqueId
                          }
                        }
                      }
                      ... on VulnerableAssetContainer {
                        ImageExternalId
                        VmExternalId
                        ServerlessContainer
                        PodNamespace
                        PodName
                        NodeName
                      }
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

        if response.get("errors") is not None:
            raise WizErrors.from_response(response)

        return WizResult.from_vulnerability_findings_response(response)
