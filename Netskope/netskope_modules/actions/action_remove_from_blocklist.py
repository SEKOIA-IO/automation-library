from pydantic import Field

from netskope_modules.actions.action_base import NetskopeAction, NetskopeActionArguments


class RemoveFromBlocklistArguments(NetskopeActionArguments):
    blocklist_id: str = Field(..., description="The ID of the blocklist")
    items: list[str] = Field(..., description="List of items in the blocklist (IPs, domains, or URLs)")
    sort_items: bool = Field(True, description="Sort items alphabetically")


class RemoveFromBlocklistAction(NetskopeAction):
    """
    Remove URL entries from an existing Netskope blocklist.
    """

    def run(self, arguments: dict) -> None:
        args = RemoveFromBlocklistArguments(**arguments)
        self.initialize_action_arguments(args)

        current_blocklist = self.get_blocklist(args.blocklist_id)
        blocklist_name = current_blocklist.get("name", "unknown")
        blocklist_type = current_blocklist.get("data", {}).get("type", "exact")

        provided_count = len(args.items)
        existing_items = self.extract_urls(current_blocklist)

        # Normalize incoming values once (trim, deduplicate, keep input order).
        normalized_items = self.normalize_urls(args.items, sort_items=False)
        # Keep only requested entries that currently exist in the blocklist.
        items_to_remove = [item for item in normalized_items if item in set(existing_items)]

        # Count requested non-empty entries that are not currently present.
        missing_count = sum(
            1
            for item in (item.strip() for item in args.items if item and item.strip())
            if item not in set(existing_items)
        )
        removed_count = len(items_to_remove)

        if not items_to_remove:
            self.log(
                level="info",
                message=(
                    f"No item(s) removed from blocklist {blocklist_name} "
                    f"(id = {args.blocklist_id}): 0/{provided_count} removed ({missing_count} already missing)"
                ),
            )
            return

        # Rebuild the full blocklist by excluding the items to remove.
        remaining_items = [item for item in existing_items if item not in set(items_to_remove)]
        remaining_items = self.normalize_urls(remaining_items, sort_items=args.sort_items)
        blocklist_name = self.execute_request(
            "PATCH",
            f"api/v2/policy/urllist/{args.blocklist_id}/replace",
            json={"data": {"type": blocklist_type, "urls": remaining_items}, "name": blocklist_name},
        ).get("name", blocklist_name)

        # Deploy the changes
        self.deploy_blocklist_changes()

        self.log(
            level="info",
            message=(
                f"Successfully removed from blocklist {blocklist_name} "
                f"(id = {args.blocklist_id}): {removed_count}/{provided_count} removed ({missing_count} already missing)"
            ),
        )
