from time import sleep


from sekoia_automation.action import Action
from sekoia_automation.exceptions import MissingActionArgumentError


class UtilsWait(Action):
    """
    Action to wait N seconds
    """

    MAX_TIME_TO_WAIT = 3600  # 1 hour

    def run(self, arguments) -> None:
        time_to_wait = arguments.get("duration")

        if time_to_wait is None:
            raise MissingActionArgumentError("duration")

        elif type(time_to_wait) != int:
            raise ValueError("Duration should be an integer")

        elif time_to_wait < 0:
            raise ValueError("Duration can't be negative")

        elif time_to_wait >= self.MAX_TIME_TO_WAIT:
            raise ValueError("Wait duration is too long. Please don't exceed %d second(s)" % self.MAX_TIME_TO_WAIT)

        sleep(time_to_wait)
