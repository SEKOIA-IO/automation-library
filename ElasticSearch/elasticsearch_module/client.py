from functools import cached_property
from typing import Any, Optional

import elasticsearch
from elastic_transport import ObjectApiResponse
from elastic_transport._models import DEFAULT
from tenacity import Retrying, retry_if_not_exception_type, stop_after_delay, wait_exponential


class ElasticSearchError(Exception):
    def __init__(self, message: str | None = None) -> None:
        super().__init__(message)
        self.message = message


class ElasticSearchApiError(ElasticSearchError):
    def __init__(self, message: str | None = None, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.message = message

    @classmethod
    def from_response(cls, response: dict[str, Any]) -> Optional["ElasticSearchApiError"]:
        if "error" in response:
            error = response["error"]
            status_code = response.get("status")
            message = error.get("reason") or error.get("message")

            return cls(message=message, status_code=status_code)

        return None


class ElasticSearchClient(object):
    """
    Client for ElasticSearch API.
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        disable_certificate_verification: bool | None = None,
        sha256_tls_fingerprint: str | None = None,
    ):
        self.verify_certs = False
        if disable_certificate_verification is not None:  # pragma: no cover
            self.verify_certs = not disable_certificate_verification

        self.url = url
        self.api_key = api_key
        self.sha256_tls_fingerprint = sha256_tls_fingerprint

    @cached_property
    def _client(self) -> elasticsearch.Elasticsearch:
        return elasticsearch.Elasticsearch(
            hosts=self.url,
            api_key=self.api_key,
            verify_certs=self.verify_certs,
            ssl_assert_fingerprint=self.sha256_tls_fingerprint or DEFAULT,
            ssl_show_warn=False,
        )

    def _wait_for_result(self, query_id: str, timeout: int = 60, drop_null_columns: bool | None = None) -> None:
        for attempt in Retrying(
            stop=stop_after_delay(timeout),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
            retry=retry_if_not_exception_type(ElasticSearchApiError),
        ):
            with attempt:
                result: dict[str, Any] = self._get_query_result(query_id, drop_null_columns=drop_null_columns).body

                possible_error = ElasticSearchApiError.from_response(result)
                if possible_error:
                    raise possible_error

                return

    def _query(self, query: str, drop_null_columns: bool | None = None) -> ObjectApiResponse[Any]:  # pragma: no cover
        return self._client.esql.async_query(
            query=query,
            format="json",
            drop_null_columns=drop_null_columns,
            # automatically delete results if response time less then `wait_for_completion_timeout`
            # this two configurations does not work with lib for some reason. However it works with api
            # keep_on_completion=False,
            # wait_for_completion_timeout="0s"
        )

    def _get_query_result(
        self, query_id: str, drop_null_columns: bool | None = None
    ) -> ObjectApiResponse[Any]:  # pragma: no cover
        return self._client.esql.async_query_get(
            id=query_id,
            drop_null_columns=drop_null_columns,
        )

    def _delete_query_result(self, query_id: str) -> ObjectApiResponse[Any]:
        return self._client.esql.async_query_delete(id=query_id)

    def execute_query(self, query: str, drop_null_columns: bool | None = None) -> list[dict[str, Any]]:
        response: dict[str, Any] = self._query(query, drop_null_columns).body

        query_id: str | None = response.get("id")

        if not response.get("is_running", True):
            if query_id is not None:
                self._delete_query_result(query_id)

            return self.map_response_to_result(response)

        if query_id is None:  # pragma: no cover
            raise ElasticSearchError("ElasticSearch response does not contain a query id to fetch result")

        self._wait_for_result(query_id)

        final_response: dict[str, Any] = self._get_query_result(query_id).body

        self._delete_query_result(query_id)

        return self.map_response_to_result(final_response)

    @classmethod
    def map_response_to_result(cls, response: dict[str, Any]) -> list[dict[str, Any]]:
        columns: list[dict[str, Any]] = response.get("columns", [])
        values: list[list[Any]] = response.get("values", [])

        return [{col["name"]: value for col, value in zip(columns, row)} for row in values]
