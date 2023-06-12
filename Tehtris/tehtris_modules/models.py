from pydantic import BaseModel, Field

from tehtris_modules.constants import API_BASE_URL_FORMAT


class TehtrisModuleConfiguration(BaseModel):
    apikey: str = Field(..., description="The APIkey to authenticate call to the API")
    tenant_id: str = Field(..., description="The identifier of the tenant")

    @property
    def base_url(self) -> str:
        return API_BASE_URL_FORMAT.format(tenant_id=self.tenant_id)
