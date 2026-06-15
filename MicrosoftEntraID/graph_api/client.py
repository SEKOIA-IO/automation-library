from datetime import datetime, timezone
from typing import AsyncGenerator, Iterable
from urllib.parse import quote_plus, urlsplit

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


class GraphApi(object):
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        use_beta_signin_api: bool = False,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._tenant_id = tenant_id
        self._use_beta_signin_api = use_beta_signin_api
        self._client: GraphServiceClient | None = None
        self._credentials: ClientSecretCredential | None = None

    @property
    def client(self) -> GraphServiceClient:  # pragma: no cover
        if self._credentials is None:
            self._credentials = ClientSecretCredential(
                tenant_id=self._tenant_id,
                client_id=self._client_id,
                client_secret=self._client_secret,
            )

            self._client = None

        if self._client is None:
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

    def _build_signin_beta_url(self, start_date: datetime, end_date: datetime | None = None) -> str:
        filter_value = self._build_filter("createdDateTime", start_date, end_date)
        order_by = "createdDateTime asc"
        adapter_base_url = getattr(self.client.request_adapter, "base_url", "https://graph.microsoft.com/v1.0/")
        if not isinstance(adapter_base_url, str) or len(adapter_base_url) == 0:
            adapter_base_url = "https://graph.microsoft.com/v1.0/"

        parsed_base_url = urlsplit(adapter_base_url)
        graph_root_url = (
            f"{parsed_base_url.scheme}://{parsed_base_url.netloc}"
            if parsed_base_url.scheme and parsed_base_url.netloc
            else "https://graph.microsoft.com"
        )

        return (
            f"{graph_root_url}/beta/auditLogs/signIns"
            f"?$filter={quote_plus(filter_value)}"
            f"&$orderby={quote_plus(order_by)}"
        )

    async def get_signin_logs(
        self, start_date: datetime, end_date: datetime | None = None
    ) -> AsyncGenerator[SignIn, None]:
        if self._use_beta_signin_api:
            next_data_link: str | None = self._build_signin_beta_url(start_date, end_date)
            while next_data_link is not None:
                response = await self.client.audit_logs.sign_ins.with_url(next_data_link).get()
                if response is None:
                    return

                next_data_link = response.odata_next_link
                items = response.value or []
                for item in items:
                    yield item

            return

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

        next_data_link: str | None = response.odata_next_link
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
    def encode_log(value: Parsable) -> str:
        writer = _factory.get_serialization_writer("application/json")
        writer.write_object_value(None, value)

        return writer.get_serialized_content().decode("utf-8")

    async def close(self) -> None:  # pragma: no cover
        if self._client:
            self._client = None

        if self._credentials:
            await self._credentials.close()
            self._credentials = None
