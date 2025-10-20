from typing import Any, Optional, List

from sekoia_automation.action import Action
from thehive4py.types.comment import InputComment, OutputComment

from .thehiveconnector import TheHiveConnector


class TheHiveCreateCommentV5(Action):
    def run(self, arguments: dict[str, Any]) -> Optional[OutputComment]:
        api = TheHiveConnector(
            self.module.configuration["base_url"],
            self.module.configuration["apikey"],
            organisation=self.module.configuration["organisation"],
        )

        arg_alert_id = arguments["alert_id"]
        arg_message = arguments["message"]

        try:
            comment = InputComment(message=arg_message)
            return api.comment_add_in_alert(arg_alert_id, comment)
        except Exception as e:
            print("Error:", e)

        return None
