from pydantic import BaseModel, Field


class GithubModuleConfiguration(BaseModel):
    org_name: str = Field(..., description="The name of your Github organization")
    apikey: str = Field(secret=True, description="The APIkey to authenticate call to the Github API")
    pem_file: str = Field(secret=True, description="Pem file to interact with Github API")
    app_id: int = Field(..., description="Github app id to interact with Github API")
