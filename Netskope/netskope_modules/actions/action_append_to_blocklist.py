from typing import Literal

from pydantic import Field

from netskope_modules.actions.action_base import NetskopeAction, NetskopeActionArguments


class AppendToBlocklistArguments(NetskopeActionArguments):
    blocklist_id: str = Field(..., description="The ID of the blocklist")
    blocklist_type: Literal["exact", "regex"] = Field("exact", description="The type of the blocklist (exact, regex)")
    items: list[str] = Field(..., description="List of items in the blocklist (IPs, domains, or URLs)")
    sort_items: bool = Field(True, description="Sort items alphabetically")


class AppendToBlocklistAction(NetskopeAction):
    """
    Append IP addresses, domains, or URLs to an existing Netskope blocklist.
    """

    def run(self, arguments: dict) -> None:
        args = AppendToBlocklistArguments(**arguments)
        self.initialize_action_arguments(args)

        current_blocklist = self.get_blocklist(args.blocklist_id)
        blocklist_name = current_blocklist.get("name", "unknown")
        provided_count = len(args.items)
        existing_urls = set(self.extract_urls(current_blocklist))
        normalized_items = self.normalize_urls(args.items, sort_items=args.sort_items)
        items_to_append = [item for item in normalized_items if item not in existing_urls]
        added_count = len(items_to_append)
        # Count duplicates/matches against existing entries for clear operator feedback.
        duplicates_count = provided_count - added_count

        if not items_to_append:
            self.log(
                level="info",
                message=(
                f"No new item(s) appended to blocklist {blocklist_name} "
                f"(id = {args.blocklist_id}): 0/{provided_count} added ({duplicates_count} duplicates)"
                ),
            )
            return None

        # Append items to the blocklist
        append_payload = {
            "data": {
                "type": args.blocklist_type,
                "urls": items_to_append,
            }
        }

        append_response = self.execute_request(
            "PATCH", f"api/v2/policy/urllist/{args.blocklist_id}/append", json=append_payload
        )

        # Deploy the changes
        self.deploy_blocklist_changes()
        blocklist_name = append_response.get("name", blocklist_name)

        self.log(
            level="info",
            message=(
                f"Successfully appended to blocklist {blocklist_name} "
                f"(id = {args.blocklist_id}): {added_count}/{provided_count} added ({duplicates_count} duplicates)"
            ),
        )
        return None
