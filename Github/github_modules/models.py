"""Contains the models for configuration of the github connector."""

from pydantic import BaseModel, Field


class GithubModuleConfiguration(BaseModel):
    """Contains all necessary configuration to interact with Github API."""

    base_url: str = Field(
        "https://api.github.com",
        description="The base URL (e.g https://api.SUBDOMAIN.ghe.com)",
    )
    org_name: str = Field(..., description="The name of your Github organization")
    apikey: str | None = Field(
        None,
        description="The APIkey to authenticate call to the Github API",
        json_schema_extra={"secret": True},
    )
    pem_file: str | None = Field(
        None,
        description="Pem file to interact with Github API",
        json_schema_extra={"secret": True},
    )
    app_id: int | None = Field(
        None, description="Github app id to interact with Github API"
    )
