from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field
from sekoia_automation.action import Action


class Arguments(BaseModel):
    # this will remain for the backward compatibility
    selected_timezone: Annotated[
        Literal[
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
        | None,
        Field(alias="selectedTimezone"),
    ] = None

    selected_named_timezone: Annotated[str | None, Field(alias="selectedNamedTimezone")] = None


class GetCurrentTimeAction(Action):
    """
    Action to get current time and return it
    """

    def _utc_to_gmt(self, value):
        offset_hours = int(value.split(" ")[1].strip())

        current_time = datetime.now(UTC).replace(tzinfo=None)

        result_time = current_time + timedelta(hours=offset_hours)

        return result_time

    def run(self, ra: Arguments) -> dict:
        if not ra.selected_named_timezone and not ra.selected_timezone:
            self.log(message="You should set a timezone", level="error")
            raise ValueError("No timezone defined in the configuration")

        # new field has a higher priority
        if ra.selected_named_timezone:
            self.log(message=f"Retrieving current time for {ra.selected_named_timezone}", level="info")
            try:
                tz = ZoneInfo(ra.selected_named_timezone)

            except ZoneInfoNotFoundError as err:
                self.log_exception(err)
                raise ValueError(f"Invalid timezone: {ra.selected_named_timezone}")

            # we need to get time in correct timezone, but we don't need the timezone itself
            date_to_return = datetime.now(tz).replace(tzinfo=None)

        else:
            self.log(message=f"Retrieving current time for {ra.selected_timezone}", level="info")
            date_to_return = self._utc_to_gmt(ra.selected_timezone)

        return {
            "epoch": int(date_to_return.timestamp()),
            "iso8601": date_to_return.isoformat(),
        }
