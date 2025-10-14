from datetime import datetime, timezone
from functools import cached_property
from typing import Any, AsyncGenerator, Iterable, TypeVar

import orjson
from azure.identity.aio import ClientSecretCredential
from kiota_abstractions.base_request_configuration import RequestConfiguration
from kiota_abstractions.serialization import Parsable
from kiota_serialization_json.json_serialization_writer_factory import JsonSerializationWriterFactory
from msgraph import GraphServiceClient
from msgraph.generated.audit_logs.directory_audits.directory_audits_request_builder import (
    DirectoryAuditsRequestBuilder,
)
from msgraph.generated.audit_logs.sign_ins.sign_ins_request_builder import SignInsRequestBuilder
from msgraph.generated.models.directory_audit import DirectoryAudit
from msgraph.generated.models.sign_in import SignIn

_factory = JsonSerializationWriterFactory()

ParsableT = TypeVar("ParsableT", bound=Parsable)


class GraphApi(object):
    def __init__(self, client_id: str, client_secret: str, tenant_id: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._tenant_id = tenant_id
        self._client: GraphServiceClient | None = None
        self._credentials: ClientSecretCredential | None = None

    @cached_property
    def client(self) -> GraphServiceClient:  # pragma: no cover
        if self._client is None:
            self._credentials = ClientSecretCredential(
                tenant_id=self._tenant_id,
                client_id=self._client_id,
                client_secret=self._client_secret,
            )

            self._client = GraphServiceClient(
                credentials=self._credentials,
                scopes=["https://graph.microsoft.com/.default"],
            )

        return self._client

    @staticmethod
    def _format_date(dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def _build_filter(
        self, field: str, start: datetime, end: datetime | None = None, extra: Iterable[str] = ()
    ) -> str:
        parts: list[str] = [f"{field} ge {self._format_date(start)}"]
        if end:
            parts.append(f"{field} le {self._format_date(end)}")

        parts.extend(extra)

        return " and ".join(parts) if parts else ""

    async def get_signin_logs(
        self, start_date: datetime, end_date: datetime | None = None
    ) -> AsyncGenerator[SignIn, None]:
        request_configuration = RequestConfiguration(
            query_parameters=SignInsRequestBuilder.SignInsRequestBuilderGetQueryParameters(
                filter=self._build_filter("createdDateTime", start_date, end_date),
                orderby=["createdDateTime asc"],
            ),
        )

        response = await self.client.audit_logs.sign_ins.get(request_configuration=request_configuration)
        if response is None:
            return

        next_data_link = response.odata_next_link
        items = response.value or []
        for item in items:
            yield item

        # Follow @odata.nextLink
        while next_data_link is not None:
            next_link_response = await self.client.audit_logs.sign_ins.with_url(next_data_link).get()
            if next_link_response is None:
                return

            next_data_link = next_link_response.odata_next_link
            items = next_link_response.value or []
            for item in items:
                yield item

    async def get_directory_audit_logs(
        self, start_date: datetime, end_date: datetime | None = None
    ) -> AsyncGenerator[DirectoryAudit, None]:
        request_configuration = RequestConfiguration(
            query_parameters=DirectoryAuditsRequestBuilder.DirectoryAuditsRequestBuilderGetQueryParameters(
                filter=self._build_filter("activityDateTime", start_date, end_date),
                orderby=["activityDateTime asc"],
            )
        )

        response = await self.client.audit_logs.directory_audits.get(request_configuration=request_configuration)
        if response is None:
            return

        next_data_link = response.odata_next_link
        items = response.value or []
        for item in items:
            yield item

        # Follow @odata.nextLink
        while next_data_link is not None:
            next_link_response = await self.client.audit_logs.directory_audits.with_url(next_data_link).get()
            if next_link_response is None:
                return

            next_data_link = next_link_response.odata_next_link
            items = next_link_response.value or []
            for item in items:
                yield item

    @staticmethod
    def encode_value(value: Parsable) -> str:
        writer = _factory.get_serialization_writer("application/json")
        writer.write_object_value(None, value)

        return writer.get_serialized_content().decode("utf-8")

    @staticmethod
    def encode_value_as_dict(value: Parsable) -> dict[str, Any]:
        writer = _factory.get_serialization_writer("application/json")
        writer.write_object_value(None, value)

        result: dict[str, Any] = orjson.loads(writer.get_serialized_content())
        return result

    @staticmethod
    def encode_values_as_dict(key: str | None, values: list[ParsableT]) -> dict[str, Any]:
        writer = _factory.get_serialization_writer("application/json")
        writer.write_collection_of_object_values(key, values)
        result: dict[str, Any] = orjson.loads(writer.get_serialized_content())

        return result

    async def close(self) -> None:  # pragma: no cover
        if self._credentials:
            await self._credentials.close()
            self._credentials = None
