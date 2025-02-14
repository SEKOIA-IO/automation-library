from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

from sekoia_automation.connector import DefaultConnectorConfiguration


class MicrosoftSentinelConfiguration(BaseModel):
    tenant_id: str = Field(..., description="Tenant ID")
    client_id: str = Field(..., description="Client ID ")
    client_secret: str = Field(secret=True, description="Client Secret")
    subscription_id: str = Field(..., description="Subscription ID")
    resource_group: str = Field(..., description="Resource Group")
    workspace_name: str = Field(..., description="Workspace Name")


class MicrosoftSentinelConnectorConfiguration(DefaultConnectorConfiguration):
    chunk_size: int = 1000
    frequency: int = 60


class OwnerModel(BaseModel):
    additional_properties: Dict[str, Any]
    assigned_to: str | None
    email: str | None
    user_principal_name: str | None
    object_id: str | None


class AdditionalDataModel(BaseModel):
    additional_properties: Dict[str, Any]
    alerts_count: int | None
    bookmarks_count: int | None
    comments_count: int | None
    alert_product_names: List[str]
    tactics: List[str]


class MicrosoftSentinelResponseModel(BaseModel):
    additional_properties: Dict[str, Any]
    id: str
    name: str
    type: str
    system_data: Optional[str]
    etag: str
    additional_data: AdditionalDataModel
    classification: Optional[str]
    classification_comment: Optional[str]
    classification_reason: Optional[str]
    created_time_utc: Optional[str]
    description: Optional[str]
    incident_url: Optional[str]
    incident_number: Optional[int]
    labels: Optional[List[str]]
    last_activity_time_utc: Optional[str]
    last_modified_time_utc: Optional[str]
    owner: OwnerModel
    related_analytic_rule_ids: Optional[List[str]]
    severity: Optional[str]
    status: Optional[str]
    title: Optional[str]
