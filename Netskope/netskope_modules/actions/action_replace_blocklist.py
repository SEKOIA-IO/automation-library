from typing import Literal

from pydantic import Field

from netskope_modules.actions.action_base import NetskopeActionArguments
from netskope_modules.actions.action_blocklist_base import NetskopeBlocklistAction


class ReplaceBlocklistArguments(NetskopeActionArguments):
    blocklist_id: str = Field(..., description="The ID of the blocklist")
    blocklist_name: str = Field(..., description="The name of the blocklist")
    blocklist_type: Literal["exact", "regex"] = Field("exact", description="The type of the blocklist (exact, regex)")
    items: list[str] = Field(..., description="List of items in the blocklist (IPs, domains, or URLs)")
    sort_items: bool = Field(True, description="Sort items alphabetically")


class ReplaceBlocklistAction(NetskopeBlocklistAction):
    """
    Replace an entire Netskope blocklist with new items.
    """

    def run(self, arguments: dict) -> dict:
        args = ReplaceBlocklistArguments(**arguments)
        self.initialize_action_arguments(args)
        current_blocklist = self.get_blocklist(args.blocklist_id)
        normalized_items = self.normalize_urls(args.items, sort_items=args.sort_items)

        # Replace the entire blocklist
        replace_payload = {
            "data": {"type": args.blocklist_type, "urls": normalized_items},
            "name": args.blocklist_name,
        }

        replace_response = self.execute_request(
            "PATCH", f"api/v2/policy/urllist/{args.blocklist_id}/replace", json=replace_payload
        )
        replace_request = self.get_last_api_request()
        blocklist_name = replace_response.get("name", args.blocklist_name)

        # Deploy the changes
        self.deploy_blocklist_changes()

        return self.build_blocklist_result(
            action_name="replace_blocklist",
            api_request=replace_request,
            action_response=replace_response,
            status=(
                f"Successfully replaced blocklist {blocklist_name} "
                f"(id = {args.blocklist_id}) with {len(normalized_items)} item(s)"
            ),
        )
