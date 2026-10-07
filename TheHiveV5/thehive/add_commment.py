from typing import Annotated, Optional

from pydantic import BaseModel, Field, StringConstraints
from sekoia_automation.action import Action
from thehive4py.types.comment import InputComment, OutputComment

from .thehiveconnector import TheHiveConnector

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class TheHiveCreateCommentArguments(BaseModel):
    alert_id: NonEmptyStr = Field(..., description="The Unique identifier of the alert")
    message: NonEmptyStr = Field(..., description="Comment message")


class TheHiveCreateCommentV5(Action):
    def run(self, arguments: TheHiveCreateCommentArguments) -> Optional[OutputComment]:
        api = TheHiveConnector(
            self.module.configuration["base_url"],
            self.module.configuration["apikey"],
            organisation=self.module.configuration["organisation"],
            verify=self.module.configuration.get("verify_certificate", True),
            ca_certificate=self.module.configuration.get("ca_certificate"),
            log_fn=self.log,
        )

        arg_alert_id = arguments.alert_id
        arg_message = arguments.message

        comment = InputComment(message=arg_message)
        return api.comment_add_in_alert(arg_alert_id, comment)
