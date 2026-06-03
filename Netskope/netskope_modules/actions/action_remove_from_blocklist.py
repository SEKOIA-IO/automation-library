from pydantic import Field

from netskope_modules.actions.action_base import NetskopeActionArguments
from netskope_modules.actions.action_blocklist_base import NetskopeBlocklistAction


class RemoveFromBlocklistArguments(NetskopeActionArguments):
    blocklist_id: str = Field(..., description="The ID of the blocklist")
    items: list[str] = Field(..., description="List of items in the blocklist (IPs, domains, or URLs)")
    sort_items: bool = Field(True, description="Sort items alphabetically")


class RemoveFromBlocklistAction(NetskopeBlocklistAction):
    """
    Remove URL entries from an existing Netskope blocklist.
    """

    def run(self, arguments: dict) -> dict:
        args = RemoveFromBlocklistArguments(**arguments)
        self.initialize_action_arguments(args)

        current_blocklist = self.get_blocklist(args.blocklist_id)
        blocklist_name = current_blocklist.get("name", "unknown")
        blocklist_type = current_blocklist.get("data", {}).get("type", "exact")

        provided_count = len(args.items)
        cleaned_items = [item.strip() for item in args.items if item.strip()]

        existing_items = self.extract_urls(current_blocklist)
        existing_set = set(existing_items)
        missing_count = sum(1 for item in cleaned_items if item not in existing_set)
        normalized_items = self.normalize_urls(args.items, sort_items=False)
        items_to_remove = [item for item in normalized_items if item in existing_set]
        removed_count = len(items_to_remove)

        if not items_to_remove:
            return self.build_blocklist_result(
                action_name="remove_from_blocklist",
                api_request=self.get_last_api_request(),
                action_response=current_blocklist,
                status=(
                    f"No item(s) removed from blocklist {blocklist_name} "
                    f"(id = {args.blocklist_id}): 0/{provided_count} removed ({missing_count} already missing)"
                ),
            )

        remaining_items = [item for item in existing_items if item not in set(items_to_remove)]
        remaining_items = self.normalize_urls(remaining_items, sort_items=args.sort_items)

        replace_payload = {
            "data": {
                "type": blocklist_type,
                "urls": remaining_items,
            },
            "name": blocklist_name,
        }

        remove_response = self.execute_request(
            "PATCH",
            f"api/v2/policy/urllist/{args.blocklist_id}/replace",
            json=replace_payload,
        )
        remove_request = self.get_last_api_request()
        blocklist_name = remove_response.get("name", blocklist_name)

        # Deploy the changes
        self.deploy_blocklist_changes()

        return self.build_blocklist_result(
            action_name="remove_from_blocklist",
            api_request=remove_request,
            action_response=remove_response,
            status=(
                f"Successfully removed from blocklist {blocklist_name} "
                f"(id = {args.blocklist_id}): {removed_count}/{provided_count} removed ({missing_count} already missing)"
            ),
        )
