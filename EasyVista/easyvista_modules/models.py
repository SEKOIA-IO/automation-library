from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


class RequestItem(BaseModel):
    catalog_code: str | None = Field(default=None, description="Catalog entry code; determines the ticket workflow")
    title: str | None = None
    description: str | None = Field(default=None, description="Ticket description, stored in the COMMENT field")
    urgency_id: int | None = None
    impact_id: str | None = None
    recipient_name: str | None = None
    recipient_mail: str | None = None
    department_code: str | None = None
    location_id: int | None = None
    custom_fields: dict[str, Any] | None = Field(default=None, description="EasyVista field names, forwarded verbatim")


class CreateRequestIncidentArguments(BaseModel):
    requests: list[RequestItem] = Field(min_length=1, max_length=1, description="Exactly one ticket per call")


class ViewRequestIncidentArguments(BaseModel):
    rfc_number: str = Field(description="Ticket RFC number")


class UpdateRequestIncidentArguments(ViewRequestIncidentArguments):
    append: bool | None = Field(default=None, description="Append to the description (requires EV SM 2025.3+)")
    description: str | None = None
    urgency_id: str | None = None
    external_reference: str | None = None
    asset: str | None = None
    asset_serial: str | None = None
    ci: str | None = None
    ci_id: int | None = None
    custom_fields: dict[str, Any] | None = Field(default=None, description="EasyVista field names, forwarded verbatim")


class CloseRequestIncidentArguments(ViewRequestIncidentArguments):
    status_guid: str | None = Field(default=None, description="Final status GUID; defaults to the Closed meta-status")
    comment: str | None = None
    end_date: str | None = Field(default=None, description="Closing action date, MM/DD/YYYY HH:MM:SS")
    catalog_guid: str | None = None
    delete_actions: bool | None = None


class SuspendRequestIncidentArguments(ViewRequestIncidentArguments):
    comment: str | None = None
    done_by_id: int | None = None


class RestartRequestIncidentArguments(SuspendRequestIncidentArguments):
    pass


class ViewRequestsIncidentsListArguments(BaseModel):
    max_rows: int | None = Field(default=None, description="Page size; API default is 100. Returns a single page")
    search: str | None = Field(default=None, description="EasyVista filter expression, forwarded verbatim")
    sort: str | None = None
    fields: str | None = Field(default=None, description="Comma-separated field names")


class ViewRequestIncidentProblemArguments(ViewRequestIncidentArguments):
    pass


class ViewRequestIncidentCommentArguments(ViewRequestIncidentArguments):
    pass


class DocumentItem(BaseModel):
    filename: str
    filedata: str = Field(description="File content encoded in standard base64")


class UploadAttachDocumentRequestIncidentArguments(ViewRequestIncidentArguments):
    documents: list[DocumentItem] = Field(min_length=1)
    description: str | None = None


class GetRequestIncidentDocumentsArguments(ViewRequestIncidentArguments):
    pass


class GetRequestIncidentDocumentArguments(ViewRequestIncidentArguments):
    id: str = Field(description="DOCUMENT_ID from the documents list")


class DeleteRequestDocumentArguments(GetRequestIncidentDocumentArguments):
    pass


class RelatedActionItem(BaseModel):
    action_type_id: str | None = Field(
        default=None,
        description="Type ID; provide at least one of action_type_id, action_type_name or action_type_guid",
    )
    action_type_name: str | None = Field(
        default=None,
        description="Type name in the API user language; provide at least one type ID, name or GUID",
    )
    action_type_guid: str | None = Field(
        default=None,
        description="Type GUID (EV SM 2023.4+); provide at least one type ID, name or GUID. "
        "If the API rejects a GUID, use an action type ID or name supported by the ticket catalog",
    )
    group_id: int | None = Field(
        default=None, description="Assigned group ID; provide at least one of group_id, group_name or group_mail"
    )
    group_name: str | None = Field(
        default=None, description="Assigned group name; provide at least one of group_id, group_name or group_mail"
    )
    group_mail: str | None = Field(
        default=None, description="Assigned group email; provide at least one of group_id, group_name or group_mail"
    )
    description: str | None = None
    comment: str | None = None


class CreateRelatedActionIncidentArguments(ViewRequestIncidentArguments):
    action: RelatedActionItem


class CreateTaskRequestIncidentArguments(ViewRequestIncidentArguments):
    action_type_id: str | None = Field(
        default=None, description="Action type identifier; provide at least one of action_type_id or action_type_name"
    )
    action_type_name: str | None = Field(
        default=None,
        description="Type name in the API user language; provide at least one of action_type_id or action_type_name",
    )
    group_id: int | None = Field(
        default=None, description="Assigned group ID; provide at least one of group_id, group_name or group_mail"
    )
    group_name: str | None = Field(
        default=None, description="Assigned group name; provide at least one of group_id, group_name or group_mail"
    )
    group_mail: str | None = Field(
        default=None, description="Assigned group email; provide at least one of group_id, group_name or group_mail"
    )
    description: str | None = None
    elapsed_time: str | None = None
    time_cost: str | None = None
    contractual_cost: str | None = None
    creation_date_ut: str | None = None
    start_date_ut: str | None = None
    end_date_ut: str | None = None


class GetNonTerminatedActionsQuestionnairesArguments(BaseModel):
    current_incident: str = Field(description="Ticket RFC number")
    action_type_id: int = Field(description="Numeric action type ID from EasyVista administration; not a GUID")


class GetSpecificActionQuestionnaireArguments(GetNonTerminatedActionsQuestionnairesArguments):
    action_id: str = Field(description="ACTION_ID of the workflow action")


class EasyVistaConfiguration(BaseModel):
    base_url: str = Field(description="HTTPS protocol and host of the EasyVista server, without a path")
    tenant_id: str = Field(
        min_length=1, pattern="\\S", description="Non-empty EasyVista account number, including any leading zeros"
    )
    use_token: bool = True
    username: str | None = None
    password: str | None = Field(default=None, json_schema_extra={"secret": True})
    token: str | None = Field(default=None, json_schema_extra={"secret": True})
    verify_ssl: bool = True

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme != "https":
            raise ValueError("base_url must use HTTPS")
        if (
            not parts.hostname
            or parts.username is not None
            or parts.password is not None
            or (parts.path not in {"", "/"})
            or parts.query
            or parts.fragment
        ):
            raise ValueError("base_url must contain only a protocol and host")
        return value.rstrip("/")
