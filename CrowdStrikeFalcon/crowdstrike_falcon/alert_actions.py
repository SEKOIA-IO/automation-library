import enum
from abc import ABC
from typing import Any

from crowdstrike_falcon.action import CrowdstrikeAction
from crowdstrike_falcon.client.schemas import AlertAction, HostAction, UpdateAlertParameter


class UpdateAlertStatus(enum.Enum):
    """
    Mapping of available alert statuses based on docs.

    Possible values: closed, in_progress, new, reopened
    """

    closed = "closed"
    in_progress = "in_progress"
    new = "new"
    reopened = "reopened"


class CrowdstrikeAlertAction(CrowdstrikeAction, ABC):
    ACTION: AlertAction

    def get_action_parameters(self, arguments: dict[str, Any]) -> list[UpdateAlertParameter]:
        raise NotImplementedError

    def run(self, arguments: dict[str, Any]) -> None:
        ids: list[str] = arguments.get("ids", [])
        if not ids:
            self.error(f"List of ID`s should not be empty.")
            return

        self.log("Applying action {0} to {1} alerts".format(self.ACTION, ",".join(ids)))

        # In case of any error it will raise an exception inside client, so no need to handle pure response here.
        result = [_ for _ in self.client.update_alerts(ids, self.get_action_parameters(arguments))]

        self.log("Action applied to alerts.")


class CrowdstrikeActionUpdateAlertStatus(CrowdstrikeAlertAction):
    ACTION = AlertAction.update_status

    def get_action_parameters(self, arguments: dict[str, Any]) -> list[UpdateAlertParameter]:
        new_status = UpdateAlertStatus(arguments.get("new_status"))

        return [UpdateAlertParameter(name=self.ACTION, value=new_status.value)]


class CrowdstrikeActionCommentAlert(CrowdstrikeAlertAction):
    ACTION = AlertAction.append_comment

    def get_action_parameters(self, arguments: dict[str, Any]) -> list[UpdateAlertParameter]:
        comment = arguments.get("comment")
        if not comment:
            raise ValueError("Comment should not be empty.")

        return [UpdateAlertParameter(name=self.ACTION, value=comment)]
