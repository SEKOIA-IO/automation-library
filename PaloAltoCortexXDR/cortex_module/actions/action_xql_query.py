import time
from typing import Any

from pydantic.main import BaseModel

from cortex_module.actions import PaloAltoCortexXDRAction
from cortex_module.helper import format_fqdn


class XQLQueryArguments(BaseModel):
    """
    Arguments for the XQL query action.
    """

    query: str
    tenants: list[str] | None = None
    timeframe_from: int | None = None
    timeframe_to: int | None = None
    max_wait_time: int = 60  # in seconds


class XQLQueryAction(PaloAltoCortexXDRAction):
    """
    This action is used to quarantine files on endpoints.
    """

    start_query_uri = "public_api/v1/xql/start_xql_query"
    result_query_uri = "public_api/v1/xql/get_query_results"

    def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """
        Run the XQL query action.
        """
        model = XQLQueryArguments(**arguments)

        # Start the XQL query
        start_query_payload: dict[str, dict[str, Any]] = {
            "request_data": {
                "query": model.query,
            }
        }

        if model.tenants:
            start_query_payload["request_data"]["tenants"] = model.tenants

        if model.timeframe_from and model.timeframe_to:
            start_query_payload["request_data"]["timeframe"] = {
                "from": model.timeframe_from,
                "to": model.timeframe_to,
            }

        start_query_uri = f"{format_fqdn(self.module.configuration.fqdn)}/{self.start_query_uri}"
        start_query_response = self.client.post(url=start_query_uri, json=start_query_payload)
        start_query_response.raise_for_status()
        start_query_result: dict[str, Any] = start_query_response.json()
        self.handle_error_result(start_query_result)

        # Get the query ID from the response
        # Based on the documentation, the query ID is in the "reply" field of the response
        # https://docs-cortex.paloaltonetworks.com/r/Cortex-XDR-REST-API/Start-an-XQL-Query
        query_id = start_query_result.get("reply")

        if not query_id:
            raise ValueError("Failed to start XQL query. No query ID returned.")

        start_wait_time = time.time()
        while True:
            # Check if the query is still pending
            query_status_payload = {
                "request_data": {
                    "query_id": query_id,
                    "pending_flag": True,
                    "limit": 1000,
                    "format": "json",
                },
            }

            result_query_uri = f"{format_fqdn(self.module.configuration.fqdn)}/{self.result_query_uri}"
            result_query_response = self.client.post(url=result_query_uri, json=query_status_payload)
            result_query_response.raise_for_status()
            data_result: dict[str, Any] = result_query_response.json()
            self.handle_error_result(data_result)

            if data_result.get("reply", {}).get("status") == "pending":
                # Check if the maximum wait time has been reached
                if time.time() - start_wait_time > model.max_wait_time:
                    raise ValueError("Query execution timed out.")

                time.sleep(10)  # Wait for 10 seconds before checking again
            else:
                results: list[dict[str, Any]] = data_result["reply"].get("results", {}).get("data", [])

                return {
                    "results": results,
                }
