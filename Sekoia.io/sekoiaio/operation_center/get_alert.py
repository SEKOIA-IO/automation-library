from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from sekoia_automation.action import GenericAPIAction

from sekoiaio.operation_center.constants import base_url


class GetAlertArguments(BaseModel):
    uuid: str = Field(..., description="UUID of the alert to retrieve")
    stix: Optional[bool] = None
    cases: Optional[bool] = None

    @model_validator(mode="after")
    def validate_uuid(self) -> "GetAlertArguments":

        # emptyness check
        if not self.uuid:
            raise ValueError("UUID must not be empty")

        # short id validation
        if self.uuid.startswith("AL") and len(self.uuid) == 12:
            # If the UUID starts with "AL", we assume it's a short ID
            return self

        # UUID validation
        try:
            UUID(self.uuid)
        except ValueError:
            raise ValueError(f"Invalid UUID: {self.uuid}")

        return self


class GetAlert(GenericAPIAction):
    verb = "get"
    endpoint = base_url + "alerts/{uuid}"
    query_parameters = ["stix", "cases"]

    def run(self, arguments: GetAlertArguments) -> dict | None:
        # GenericAPIAction.run()/get_url()/get_query_parameters() expect a plain dict
        # (they `.pop()` keys off it), so convert the validated model back to one.
        return super().run(arguments.model_dump(mode="json", exclude_none=True))
