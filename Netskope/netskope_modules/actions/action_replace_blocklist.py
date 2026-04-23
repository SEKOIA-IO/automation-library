from pydantic import BaseModel, Field

from netskope_modules.actions.action_base import NetskopeAction


class ReplaceBlocklistArguments(BaseModel):
    url_list_id: str = Field(..., description="The ID of the URL list to replace")
    items: list[str] = Field(..., description="List of items to set in the blocklist (IPs, domains, or URLs)")
    name: str = Field(..., description="Name of the URL list")
    type: str = Field("exact", description="Type of URL list (exact, regex, etc.)")


class ReplaceBlocklistAction(NetskopeAction):
    """
    Replace an entire Netskope blocklist with new items.
    """

    def run(self, arguments: dict) -> dict:
        args = ReplaceBlocklistArguments(**arguments)

        # Replace the entire URL list
        replace_payload = {"data": {"type": args.type, "urls": args.items}, "name": args.name}

        replace_response = self.execute_request(
            "PATCH", f"api/v2/policy/urllist/{args.url_list_id}/replace", json=replace_payload
        )

        # Deploy the changes
        deploy_response = self.deploy_blocklist_changes()

        return {
            "replace_result": replace_response,
            "deploy_result": deploy_response,
            "message": f"Successfully replaced blocklist with {len(args.items)} item(s)",
        }
