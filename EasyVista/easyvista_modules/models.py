from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, field_validator


class RequestItem(BaseModel):
    catalog_code: str | None = Field(default=None, description="Catalog entry code; determines the ticket workflow")
    title: str | None = Field(default=None, description="Ticket title")
    description: str | None = Field(default=None, description="Ticket description, stored in the COMMENT field")
    urgency_id: int | None = Field(default=None, description="Urgency ID (tenant-specific)")
    impact_id: str | None = Field(default=None, description='Impact ID (e.g. "1")')
    recipient_name: str | None = Field(default=None, description="Recipient full name")
    recipient_mail: str | None = Field(default=None, description="Recipient email")
    department_code: str | None = Field(default=None, description="Department code")
    location_id: int | None = Field(default=None, description="Location ID")
    custom_fields: dict[str, Any] | None = Field(
        default=None, description="Additional EasyVista fields (field name: value), forwarded verbatim"
    )


class CreateRequestIncidentArguments(BaseModel):
    requests: list[RequestItem] = Field(
        min_length=1, max_length=1, description="Ticket to create; exactly one per call"
    )


class ViewRequestIncidentArguments(BaseModel):
    rfc_number: str = Field(description="Ticket RFC number")


class UpdateRequestIncidentArguments(ViewRequestIncidentArguments):
    append: bool | None = Field(
        default=None,
        description="Append description to the existing text, separated by <br><br> (EV SM 2025.3+); "
        "false or unset: replace it",
    )
    description: str | None = Field(
        default=None, description="Ticket description, stored in the COMMENT field; replaced unless append is true"
    )
    urgency_id: str | None = Field(default=None, description="Urgency ID (tenant-specific)")
    external_reference: str | None = Field(default=None, description="External reference (e.g. the Sekoia alert ID)")
    asset: str | None = Field(default=None, description="Asset tag")
    asset_serial: str | None = Field(default=None, description="Asset serial number")
    ci: str | None = Field(default=None, description="Configuration item name")
    ci_id: int | None = Field(default=None, description="Configuration item ID")
    custom_fields: dict[str, Any] | None = Field(
        default=None, description="Additional EasyVista fields (field name: value), forwarded verbatim"
    )


class CloseRequestIncidentArguments(ViewRequestIncidentArguments):
    status_guid: str | None = Field(default=None, description="Final status GUID; defaults to the Closed meta-status")
    comment: str | None = Field(default=None, description="Closing action comment")
    end_date: str | None = Field(
        default=None,
        description="Closing date of the ongoing actions and of the closing action (MM/DD/YYYY HH:MM:SS); "
        "defaults to now",
    )
    catalog_guid: str | None = Field(
        default=None, description="Catalog (topic) GUID; only needed to requalify the ticket before closing"
    )
    delete_actions: bool | None = Field(default=None, description="Delete the ongoing actions of the ticket")


class SuspendRequestIncidentArguments(ViewRequestIncidentArguments):
    comment: str | None = Field(default=None, description="Suspend action comment; does not change the ticket comment")
    done_by_id: int | None = Field(default=None, description="Employee ID recorded as the author")


class RestartRequestIncidentArguments(SuspendRequestIncidentArguments):
    comment: str | None = Field(default=None, description="Restart action comment")


class ViewRequestsIncidentsListArguments(BaseModel):
    max_rows: int | None = Field(default=None, ge=1, description="Page size (API default: 100); returns a single page")
    search: str | None = Field(default=None, description="EasyVista filter expression, forwarded verbatim")
    sort: str | None = Field(default=None, description="Sort expression (e.g. submit_date_ut desc)")
    fields: str | None = Field(default=None, description="Comma-separated field names to return")


class ViewRequestIncidentProblemArguments(ViewRequestIncidentArguments):
    pass


class ViewRequestIncidentCommentArguments(ViewRequestIncidentArguments):
    pass


class DocumentItem(BaseModel):
    filename: str = Field(description="File name with extension; becomes the document title")
    filedata: str = Field(description="File content (standard base64)")


class UploadAttachDocumentRequestIncidentArguments(ViewRequestIncidentArguments):
    documents: list[DocumentItem] = Field(min_length=1, description="Documents to attach; at least one")
    description: str | None = Field(default=None, description="Attached documents description")


class GetRequestIncidentDocumentsArguments(ViewRequestIncidentArguments):
    pass


class GetRequestIncidentDocumentArguments(ViewRequestIncidentArguments):
    id: str = Field(description="Document ID (DOCUMENT_ID from the documents list)")


class DeleteRequestDocumentArguments(GetRequestIncidentDocumentArguments):
    pass


class RelatedActionItem(BaseModel):
    action_type_id: str | None = Field(
        default=None,
        description="Action type ID (tenant-specific); provide at least one of action_type_id, action_type_name or "
        "action_type_guid",
    )
    action_type_name: str | None = Field(
        default=None,
        description="Action type name, in the REST API user language; provide at least one of action_type_id, "
        "action_type_name or action_type_guid",
    )
    action_type_guid: str | None = Field(
        default=None,
        description="Action type GUID (EV SM 2023.4+); provide at least one of action_type_id, action_type_name or "
        "action_type_guid; if the API rejects the GUID, use an ID or name allowed for the ticket catalog",
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
    description: str | None = Field(default=None, description="Related action description")
    comment: str | None = Field(default=None, description="Related action comment")


class CreateRelatedActionIncidentArguments(ViewRequestIncidentArguments):
    action: RelatedActionItem = Field(description="Action to create; provide one action type and one group")


class CreateTaskRequestIncidentArguments(ViewRequestIncidentArguments):
    action_type_id: str | None = Field(
        default=None,
        description="Action type ID (tenant-specific); provide at least one of action_type_id or action_type_name",
    )
    action_type_name: str | None = Field(
        default=None,
        description="Action type name, in the REST API user language; provide at least one of action_type_id or "
        "action_type_name",
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
    description: str | None = Field(default=None, description="Task description")
    elapsed_time: str | None = Field(default=None, description="Task elapsed time")
    time_cost: str | None = Field(default=None, description="Task time cost")
    contractual_cost: str | None = Field(default=None, description="Task contractual cost")
    creation_date_ut: str | None = Field(default=None, description="Task creation date (UTC)")
    start_date_ut: str | None = Field(default=None, description="Task start date (UTC)")
    end_date_ut: str | None = Field(default=None, description="Task end date (UTC)")


class GetNonTerminatedActionsQuestionnairesArguments(BaseModel):
    current_incident: str = Field(description="Ticket RFC number")
    action_type_id: int = Field(description="Action type ID (tenant-specific); not the action type GUID")


class GetSpecificActionQuestionnaireArguments(GetNonTerminatedActionsQuestionnairesArguments):
    action_id: str = Field(description="Workflow action ID (ACTION_ID)")


class EasyVistaConfiguration(BaseModel):
    base_url: str = Field(description="HTTPS protocol and host of the EasyVista server, without a path")
    tenant_id: str = Field(
        min_length=1, pattern="\\S", description="Non-empty EasyVista account number, including any leading zeros"
    )
    use_token: bool = Field(
        default=True, description="Use access token (Bearer) authentication, recommended; false: Basic authentication"
    )
    username: str | None = Field(default=None, description="REST API user login; required when use_token is false")
    password: str | None = Field(
        default=None,
        json_schema_extra={"secret": True},
        description="REST API user password; required when use_token is false",
    )
    token: str | None = Field(
        default=None,
        json_schema_extra={"secret": True},
        description="EasyVista access token; required when use_token is true",
    )
    verify_ssl: bool = Field(default=True, description="Verify the server TLS certificate")

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
