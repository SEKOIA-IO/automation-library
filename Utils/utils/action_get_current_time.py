from sekoia_automation.action import Action
from datetime import datetime, timedelta
from pydantic import BaseModel
from typing import Literal


class Arguments(BaseModel):
    selectedTimezone: Literal[
        "UTC -12",
        "UTC -11",
        "UTC -10",
        "UTC -9",
        "UTC -8",
        "UTC -7",
        "UTC -6",
        "UTC -5",
        "UTC -4",
        "UTC -3",
        "UTC -2",
        "UTC -1",
        "UTC 0",
        "UTC +1",
        "UTC +2",
        "UTC +3",
        "UTC +4",
        "UTC +5",
        "UTC +6",
        "UTC +7",
        "UTC +8",
        "UTC +9",
        "UTC +10",
        "UTC +11",
        "UTC +12",
    ]


class GetCurrentTimeAction(Action):
    """
    Action to get current time and return it
    """

    def _utc_to_gmt(self, value):
        offset_hours = int(value.split(" ")[1].strip())

        current_time = datetime.utcnow()

        result_time = current_time + timedelta(hours=offset_hours)

        return result_time

    def run(self, ra: Arguments) -> dict:
        self.log(message=f"Retrieving current time for {ra.selectedTimezone}", level="info")
        dateToReturn = self._utc_to_gmt(ra.selectedTimezone)

        return {
            "epoch": int(dateToReturn.timestamp()),
            "iso8601": dateToReturn.isoformat(),
        }
