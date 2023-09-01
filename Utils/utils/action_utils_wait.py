from time import sleep

from sekoia_automation.action import Action


class UtilsWait(Action):
    """
    Action to wait N seconds
    """

    MAX_TIME_TO_WAIT = 3600  # 1 hour

    def run(self, arguments) -> None:
        time_to_wait = arguments.get("duration", 0)

        time_to_wait = max(time_to_wait, 0)  # can't be less than 0
        time_to_wait = min(time_to_wait, self.MAX_TIME_TO_WAIT)  # can't be more than MAX_TIME_TO_WAIT

        sleep(time_to_wait)
