from pydantic import Field

from netskope_modules.actions.action_base import NetskopeAction, NetskopeActionArguments


class GetBlocklistArguments(NetskopeActionArguments):
    blocklist_id: str = Field(..., description="The ID of the blocklist")


class GetBlocklistAction(NetskopeAction):
    """
    Retrieve an existing Netskope blocklist.
    """

    def run(self, arguments: dict) -> None:
        args = GetBlocklistArguments(**arguments)
        self.initialize_action_arguments(args)

        blocklist = self.get_blocklist(args.blocklist_id)
        blocklist_name = blocklist.get("name", "unknown")

        self.log(
            level="info",
            message=f"Successfully fetched blocklist {blocklist_name} (id = {args.blocklist_id})",
        )
        return None
