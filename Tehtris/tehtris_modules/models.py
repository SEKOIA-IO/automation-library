from pydantic import BaseModel, Field

from tehtris_modules.constants import API_BASE_URL_FORMAT


class TehtrisModuleConfiguration(BaseModel):
    apikey: str = Field(secret=True, description="The APIkey to authenticate call to the API")
    tenant_id: str = Field(..., description="The identifier of the tenant")
    alternative_url: str | None = Field(None, description="The alternative url for the TEHTRIS instance")

    @property
    def normalized_alternative_url(self) -> str | None:
        """
        Return the alternative url without any ending /
        """
        if self.alternative_url:
            return self.alternative_url.strip("/")
        return None

    @property
    def base_url(self) -> str:
        if self.normalized_alternative_url:
            return self.normalized_alternative_url
        else:
            return API_BASE_URL_FORMAT.format(tenant_id=self.tenant_id)
