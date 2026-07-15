from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from sekoia_automation.action import GenericAPIAction

from sekoiaio.operation_center.constants import base_url


class GetAlertArguments(BaseModel):
    uuid: UUID = Field(..., description="UUID of the alert to retrieve")
    stix: Optional[bool] = None
    cases: Optional[bool] = None


class GetAlert(GenericAPIAction):
    verb = "get"
    endpoint = base_url + "alerts/{uuid}"
    query_parameters = ["stix", "cases"]

    def run(self, arguments: GetAlertArguments) -> dict | None:
        # GenericAPIAction.run()/get_url()/get_query_parameters() expect a plain dict
        # (they `.pop()` keys off it), so convert the validated model back to one.
        return super().run(arguments.model_dump(mode="json", exclude_none=True))
