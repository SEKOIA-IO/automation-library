from typing import Any, Optional

from pydantic import BaseModel, Field

from .action_vision_one_base import TrendMicroVisionOneBaseAction
from .models import NonEmptyStr


class UpdateAlertArguments(BaseModel):
    alert_id: NonEmptyStr = Field(..., description="The identifier of the alert")
    status: Optional[str] = None
    investigation_result: Optional[str] = None


class UpdateAlertAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: UpdateAlertArguments) -> Any:
        alert_id = arguments.alert_id
        status = arguments.status
        investigation_result = arguments.investigation_result

        base_url: str = self.module.configuration.base_url
        url = f"{base_url}/v3.0/workbench/alerts/{alert_id}"
        payload = {}
        if status:
            payload["status"] = status

        if investigation_result:
            payload["investigationResult"] = investigation_result

        response = self.client.patch(url, json=payload, timeout=60)
        return self.process_response(response)
