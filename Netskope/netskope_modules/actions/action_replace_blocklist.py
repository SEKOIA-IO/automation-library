from typing import Literal

from pydantic import Field

from netskope_modules.actions.action_base import NetskopeAction, NetskopeActionArguments


class ReplaceBlocklistArguments(NetskopeActionArguments):
    blocklist_id: str = Field(..., description="The ID of the blocklist")
    blocklist_type: Literal["exact", "regex"] = Field(
        "exact", description="The type of the blocklist (exact, regex)"
    )
    items: list[str] = Field(
        ..., description="List of items in the blocklist (IPs, domains, or URLs)"
    )
    sort_items: bool = Field(True, description="Sort items alphabetically")


class ReplaceBlocklistAction(NetskopeAction):
    """
    Replace an entire Netskope blocklist with new items.
    """

    def run(self, arguments: dict) -> None:
        args = ReplaceBlocklistArguments(**arguments)
        self.initialize_action_arguments(args)
        normalized_items = self.normalize_urls(args.items, sort_items=args.sort_items)

        # Replace the entire blocklist.
        blocklist_name = self.execute_request(
            "PATCH",
            f"api/v2/policy/urllist/{args.blocklist_id}/replace",
            json={"data": {"type": args.blocklist_type, "urls": normalized_items}},
        ).get("name", "unknown")

        # Deploy the changes
        self.deploy_blocklist_changes()

        self.log(
            level="info",
            message=(
                f"Successfully replaced blocklist {blocklist_name} "
                f"(id = {args.blocklist_id}) with {len(normalized_items)} item(s)"
            ),
        )
