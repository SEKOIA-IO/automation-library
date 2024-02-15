"""Contains the models for configuration of the github connector."""

from pydantic import BaseModel, Field


class GithubModuleConfiguration(BaseModel):
    """Contains all necessary configuration to interact with Github API."""

    org_name: str = Field(description="The name of your Github organization")
    apikey: str | None = Field(
        default=None, required=False, secret=True, description="The APIkey to authenticate call to the Github API"
    )
    pem_file: str | None = Field(
        default=None, required=False, secret=True, description="Pem file to interact with Github API"
    )
    app_id: int | None = Field(default=None, required=False, description="Github app id to interact with Github API")
