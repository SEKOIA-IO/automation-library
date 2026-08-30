from typing import Any

from pydantic import BaseModel, Field

from .action_vision_one_base import TrendMicroVisionOneBaseAction
from .models import NonEmptyStr


class AddAlertNoteArguments(BaseModel):
    alert_id: NonEmptyStr = Field(..., description="The identifier of the alert")
    note: NonEmptyStr = Field(..., description="The content of the note")


class AddAlertNoteAction(TrendMicroVisionOneBaseAction):
    def run(self, arguments: AddAlertNoteArguments) -> Any:
        alert_id = arguments.alert_id
        note = arguments.note

        base_url: str = self.module.configuration.base_url
        url = f"{base_url}/v3.0/workbench/alerts/{alert_id}/notes"
        payload = {"content": note}

        response = self.client.post(url, json=payload, timeout=60)
        return self.process_response(response, headers_to_include=["Location"])
