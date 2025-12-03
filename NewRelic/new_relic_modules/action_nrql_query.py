from functools import cached_property
from posixpath import join as urljoin
from typing import Any

import requests
from pydantic.v1 import BaseModel, Field
from sekoia_automation.action import Action

from . import NewRelicModule
from .client import ApiClient


class NRQLQueryActionArguments(BaseModel):
    account_ids: list[int]
    query: str


class NRQLQueryAction(Action):
    module: NewRelicModule

    @cached_property
    def client(self) -> ApiClient:
        return ApiClient(api_key=self.module.configuration.api_key)

    def handle_response_error(self, response: requests.Response) -> None:
        if not response.ok:
            level = "critical" if response.status_code in {401, 403} else "error"
            message = f"Request to NewRelic API failed with status {response.status_code} - {response.reason}"

            self.log(message=message, level=level)
            response.raise_for_status()

        raw = response.json()
        if "errors" in raw:
            message = f"Request to NewRelic API failed {response.status_code}: {raw['errors']}"
            self.log(message=message, level="error")
            raise ValueError(message)

    def run(self, arguments: NRQLQueryActionArguments) -> Any:
        url = urljoin(self.module.configuration.base_url, "graphql")

        # Do not escape double quotes, because we expect only single quotes for text values
        # (see: https://docs.newrelic.com/docs/nrql/get-started/introduction-nrql-new-relics-query-language/)
        account_list = "[%s]" % ",".join(str(account_id) for account_id in arguments.account_ids)
        query = """{ actor { nrql(accounts: %s query: "%s" timeout: 70) { results } } }""" % (
            account_list,
            arguments.query,
        )

        response = self.client.post(url, data=query)
        self.handle_response_error(response)

        return response.json()
