from typing import Any

from pydantic import BaseModel, Field
from sekoia_automation.connector import DefaultConnectorConfiguration


class MicrosoftSentinelConfiguration(BaseModel):
    tenant_id: str = Field(..., description="Tenant ID")
    client_id: str = Field(..., description="Client ID ")
    client_secret: str = Field(json_schema_extra={"secret": True}, description="Client Secret")
    subscription_id: str = Field(..., description="Subscription ID")
    resource_group: str = Field(..., description="Resource Group")
    workspace_name: str = Field(..., description="Workspace Name")


class MicrosoftSentinelConnectorConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 1000
    frequency: int = 60


class OwnerModel(BaseModel):
    additional_properties: dict[str, Any]
    assigned_to: str | None
    email: str | None
    user_principal_name: str | None
    object_id: str | None


class AdditionalDataModel(BaseModel):
    additional_properties: dict[str, Any]
    alerts_count: int | None
    bookmarks_count: int | None
    comments_count: int | None
    alert_product_names: list[str]
    tactics: list[str]


class MicrosoftSentinelResponseModel(BaseModel):
    additional_properties: dict[str, Any]
    id: str
    name: str
    type: str
    system_data: str | None
    etag: str
    additional_data: AdditionalDataModel
    classification: str | None
    classification_comment: str | None
    classification_reason: str | None
    created_time_utc: str | None
    description: str | None
    incident_url: str | None
    incident_number: int | None
    labels: list[str] | None
    last_activity_time_utc: str | None
    last_modified_time_utc: str | None
    owner: OwnerModel
    related_analytic_rule_ids: list[str] | None
    severity: str | None
    status: str | None
    title: str | None
    entities: list[dict[str, Any]] | None = None
