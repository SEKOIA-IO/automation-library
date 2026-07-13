from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TrendMicroVisionOneModuleConfiguration(BaseModel):
    base_url: str = Field(..., description="Base URL")
    api_key: str = Field(..., description="Trend Micro api_key", json_schema_extra={"secret": True})
