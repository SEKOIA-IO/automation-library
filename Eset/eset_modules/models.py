from pydantic import BaseModel, Field


class EsetModuleConfiguration(BaseModel):
    region: str = Field(..., description="Region")
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password", secret=True)
