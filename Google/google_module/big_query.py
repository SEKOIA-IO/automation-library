from functools import cached_property
from typing import Any

from google.cloud.bigquery import Client, QueryJobConfig, ScalarQueryParameter

from google_module.base import GoogleAction


class BigQueryAction(GoogleAction):
    """
    Action running a query and returning the results
    """

    @cached_property
    def client(self) -> Client:
        return Client()

    def run(self, arguments: dict[str, Any]) -> dict[str, str]:
        query = arguments["query"]
        job_config = self.get_job_config(arguments)
        query_job = self.client.query(query, job_config=job_config)
        result: dict[str, str] = self.json_result("items", [dict(row) for row in query_job])
        return result

    def get_job_config(self, arguments: dict[str, Any]) -> QueryJobConfig:
        query_parameters = [
            ScalarQueryParameter(param["name"], param["type"], param["value"])
            for param in arguments.get("parameters", [])
        ]
        return QueryJobConfig(query_parameters=query_parameters)
