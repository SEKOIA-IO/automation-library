from pydantic import Field

from netskope_modules.actions.action_base import NetskopeActionArguments
from netskope_modules.actions.action_blocklist_base import NetskopeBlocklistAction


class GetBlocklistArguments(NetskopeActionArguments):
    blocklist_id: str = Field(..., description="The ID of the blocklist")


class GetBlocklistAction(NetskopeBlocklistAction):
    """
    Retrieve an existing Netskope blocklist.
    """

    def run(self, arguments: dict) -> dict:
        args = GetBlocklistArguments(**arguments)
        self.initialize_action_arguments(args)

        blocklist = self.get_blocklist(args.blocklist_id)
        get_request = self.get_last_api_request()
        blocklist_name = blocklist.get("name", "unknown")

        return self.build_blocklist_result(
            action_name="get_blocklist",
            api_request=get_request,
            action_response=blocklist,
            status=f"Successfully fetched blocklist {blocklist_name} (id = {args.blocklist_id})",
        )
