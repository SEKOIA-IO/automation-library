from sekoia_automation.action import Action

from utils.helpers import accurate_sleep


class UtilsWait(Action):
    """
    Action to wait N seconds
    """

    MAX_TIME_TO_WAIT = 3540  # 59 minutes

    def run(self, arguments) -> None:
        time_to_wait = arguments.get("duration", 0)

        time_to_wait = max(time_to_wait, 0)  # can't be less than 0
        time_to_wait = min(time_to_wait, self.MAX_TIME_TO_WAIT)  # can't be more than MAX_TIME_TO_WAIT

        accurate_sleep(time_to_wait)
