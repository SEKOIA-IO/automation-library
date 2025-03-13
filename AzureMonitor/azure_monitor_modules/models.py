from pydantic.v1 import BaseModel, Field


class AzureMonitorModuleConfiguration(BaseModel):
    tenant_id: str = Field(..., description="ID of the Azure AD tenant")
    client_id: str = Field(
        ...,
        description="Client ID. An application needs to be created in the Azure Portal and assigned relevant permissions.",  # noqa: E501
    )
    client_secret: str = Field(
        secret=True,
        description="Client Secret associated with the registered application.",  # noqa: E501
    )
