from datetime import datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic.v1 import BaseModel
from sekoia_automation.action import Action


class Arguments(BaseModel):
    # this will remain for the backward compatibility
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
    ] | None = None

    selectedNamedTimezone: str | None = None


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
        if not ra.selectedNamedTimezone and not ra.selectedTimezone:
            self.log(message="You should set a timezone", level="error")
            return {}

        # new field has a higher priority
        if ra.selectedNamedTimezone:
            self.log(message=f"Retrieving current time for {ra.selectedNamedTimezone}", level="info")
            try:
                tz = ZoneInfo(ra.selectedNamedTimezone)

            except ZoneInfoNotFoundError as err:
                self.log_exception(err)
                return {}

            date_to_return = datetime.now(tz)

        else:
            self.log(message=f"Retrieving current time for {ra.selectedTimezone}", level="info")
            date_to_return = self._utc_to_gmt(ra.selectedTimezone)

        return {
            "epoch": int(date_to_return.timestamp()),
            "iso8601": date_to_return.isoformat(),
        }
