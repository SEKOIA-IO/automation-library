from typing import Any

from crowdstrike_falcon.action import CrowdstrikeAction
from crowdstrike_falcon.client.schemas import HostAction


class CrowdstrikeHostAction(CrowdstrikeAction):
    ACTION: HostAction

    def run(self, arguments: dict[str, Any]) -> None:
        ids: list[str] = arguments.get("ids", [])
        if not ids:
            self.error(f"List of ID`s should not be empty.")
            return

        self.log("Applying action {0} to {1} hosts".format(self.ACTION, ",".join(ids)))

        # In case of any error it will raise an exception inside client, so no need to handle pure response here.
        result = [_ for _ in self.client.host_action(ids, self.ACTION)]

        self.log("Action applied to hosts.")


class CrowdstrikeActionIsolateHosts(CrowdstrikeHostAction):
    ACTION = HostAction.contain


class CrowdstrikeActionDeIsolateHosts(CrowdstrikeHostAction):
    ACTION = HostAction.lift_containment
