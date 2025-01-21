from pydantic import BaseModel, Field


class MicrosoftOutlookModuleConfiguration(BaseModel):
    tenant_id: str = Field(..., description="ID of the Azure AD tenant")
    client_id: str = Field(
        ...,
        description="Client ID. An application needs to be created in the Azure Portal and assigned relevant "
        "permissions. Its Client ID should then be used in this configuration.",
        # noqa: E501
    )
    client_secret: str = Field(
        secret=True,
        description="Client Secret associated with the registered application. Admin Consent has to be granted to the "
        "application for it to work.",
        # noqa: E501
    )
