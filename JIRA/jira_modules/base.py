from pydantic import BaseModel, Field
from sekoia_automation.module import Module


class JIRAConfiguration(BaseModel):
    domain: str = Field(description="Your organization JIRA domain (e.g. 'sandbox.atlassian.net')")
    email: str = Field(description="User email")
    api_key: str = Field(secret=True, description="API key for the user")


class JIRAModule(Module):
    configuration: JIRAConfiguration
