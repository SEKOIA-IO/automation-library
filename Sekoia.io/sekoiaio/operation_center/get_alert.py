from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from sekoiaio.operation_center.constants import base_url
from sekoiaio.utils import FilteredQueryParametersAction


class GetAlertArguments(BaseModel):
    uuid: str = Field(..., description="The identifier (UUID or short id) of the alert to retrieve")
    stix: Optional[bool] = None
    cases: Optional[bool] = None

    @model_validator(mode="after")
    def validate_uuid(self) -> "GetAlertArguments":

        # emptiness check
        if self.uuid is None or not self.uuid.strip():
            raise ValueError("The alert identifier must not be empty")

        # short id validation
        if self.uuid.startswith("AL"):
            # If the UUID starts with "AL", we assume it's a short ID
            return self

        # UUID validation
        try:
            UUID(self.uuid)
        except ValueError:
            raise ValueError(f"Invalid alert identifier: {self.uuid}")

        return self


class GetAlert(FilteredQueryParametersAction):
    verb = "get"
    endpoint = base_url + "alerts/{uuid}"
    query_parameters = ["stix", "cases"]

    def run(self, arguments: GetAlertArguments) -> dict | None:
        # GenericAPIAction.run()/get_url()/get_query_parameters() expect a plain dict
        # (they `.pop()` keys off it), so convert the validated model back to one.
        return super().run(arguments.model_dump(mode="json", exclude_none=True))
