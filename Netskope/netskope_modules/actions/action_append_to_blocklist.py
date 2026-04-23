from pydantic import BaseModel, Field

from netskope_modules.actions.action_base import NetskopeAction


class AppendToBlocklistArguments(BaseModel):
    url_list_id: str = Field(..., description="The ID of the URL list to modify")
    items: list[str] = Field(..., description="List of items to append to the blocklist (IPs, domains, or URLs)")


class AppendToBlocklistAction(NetskopeAction):
    """
    Append IP addresses, domains, or URLs to an existing Netskope blocklist.
    """

    def run(self, arguments: dict) -> dict:
        args = AppendToBlocklistArguments(**arguments)

        # Append items to the URL list
        append_payload = {"data": {"urls": args.items}}

        append_response = self.execute_request(
            "PATCH", f"api/v2/policy/urllist/{args.url_list_id}/append", json=append_payload
        )

        # Deploy the changes
        deploy_response = self.deploy_blocklist_changes()

        return {
            "append_result": append_response,
            "deploy_result": deploy_response,
            "message": f"Successfully appended {len(args.items)} item(s) to blocklist",
        }
