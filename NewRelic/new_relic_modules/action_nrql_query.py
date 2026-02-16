import uuid
from functools import cached_property
from posixpath import join as urljoin
from typing import Any

import orjson
import requests
from pydantic.v1 import BaseModel
from sekoia_automation.action import Action

from . import NewRelicModule
from .client import ApiClient


class NRQLQueryActionArguments(BaseModel):
    account_ids: list[int]
    query: str
    save_to_file: bool = False


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

    def save_to_file(self, results: list[dict]) -> str:
        filename = str(uuid.uuid4())
        file_path = self.data_path / filename

        with file_path.open("wb") as f:
            f.write(orjson.dumps(results))

        result_path = file_path.relative_to(self.data_path)
        return str(result_path)

    def run(self, arguments: NRQLQueryActionArguments) -> Any:
        url = urljoin(self.module.configuration.base_url, "graphql")

        payload = {
            "query": "query ExecuteQuery($account_ids: [Int!], $query: Nrql!) {"
            "actor { nrql( accounts: $account_ids query: $query) { results } } "
            "}",
            "variables": {"account_ids": arguments.account_ids, "query": arguments.query},
        }
        response = self.client.post(url, json=payload)
        self.handle_response_error(response)

        content = response.json()
        results = content.get("data", {}).get("actor", {}).get("nrql", {}).get("results") or []
        if arguments.save_to_file:
            # Save to file and return its path
            path = self.save_to_file(results)
            return {"file_path": path}

        return {"results": results}
