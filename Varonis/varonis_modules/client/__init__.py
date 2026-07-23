from typing import Any

import requests
from requests.adapters import Retry
from requests_ratelimiter import LimiterAdapter

from .auth import VaronisApiAuthentication


class VaronisApiError(Exception):
    def __init__(self, js: Any) -> None:
        self.js = js


class ApiClient(requests.Session):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        ratelimit_per_second: int = 20,
        nb_retries: int = 5,
    ):
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.auth = VaronisApiAuthentication(base_url=base_url, api_key=api_key)
        self.mount(
            "https://",
            LimiterAdapter(
                per_second=ratelimit_per_second,
                max_retries=Retry(
                    total=nb_retries,
                    backoff_factor=1,
                ),
            ),
        )

    def make_request(self, query: str, variables: dict[str, Any]) -> Any:
        url = f"{self.base_url}/api/graphql"
        response = self.post(url=url, json={"query": query, "variables": variables}, timeout=60)

        raw = response.json()
        if "errors" in raw:
            raise VaronisApiError(raw)

        response.raise_for_status()

        return raw

    def alerts_async(self, from_date: str, to_date: str) -> dict[str, Any]:
        query = """query AlertsAsync($where: Alert_FilterInput!)  {
            alertsAsync(where: $where) {
                jobId
                jobStatus
                results {
                    escalationType
                    eventsCount
                    hasSensitiveResource
                    hasTaggedResource
                    id
                    isAssignedToVaronis
                    status
                    dataSource {
                        id
                        name
                        type
                    }
                    policy {
                        id
                        name
                        severity
                        category
                    }
                    generationTime {
                        dateTimeUtc
                    }
                }
            }
        }"""

        return self.make_request(
            query=query,
            variables={
                "where": {
                    "status": {"neq": "CLOSED"},
                    "generationTime": {"between": {"from": from_date, "to": to_date}},
                }
            },
        )

    def alerts_query_job(self, job_id: str) -> dict[str, Any]:
        query = """query alertsQueryJob($jobId: ID!) {
            alertsQueryJob(jobId: $jobId) {
                jobId
                jobStatus
                jobProgress
                results {
                    escalationType
                    eventsCount
                    hasSensitiveResource
                    hasTaggedResource
                    id
                    isAssignedToVaronis
                    status
                    dataSource {
                        id
                        name
                        type
                    }
                    policy {
                        id
                        name
                        severity
                        category
                    }
                    generationTime {
                        dateTimeUtc
                    }
                }
            }
        }"""

        return self.make_request(query=query, variables={"jobId": job_id})
