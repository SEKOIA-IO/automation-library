from pydantic import BaseModel, Field


class GithubModuleConfiguration(BaseModel):
    org_name: str = Field(..., description="The name of your Github organization")
    apikey: str = Field(secret=True, description="The APIkey to authenticate call to the Github API")
