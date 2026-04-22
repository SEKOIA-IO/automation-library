from pydantic import BaseModel, Field

from netskope_modules.actions.base import NetskopeAction


class AddToBlocklistArguments(BaseModel):
    url_list_id: str = Field(..., description="The ID of the URL list to modify")
    items: list[str] = Field(..., description="List of items to add to the blocklist (IPs, domains, or URLs)")


class AddToBlocklistAction(NetskopeAction):
    """
    Add IP addresses, domains, or URLs to an existing Netskope blocklist.
    """

    def run(self, arguments: dict) -> dict:
        args = AddToBlocklistArguments(**arguments)

        # Add items to the URL list
        add_payload = {
            "data": {
                "urls": args.items
            }
        }

        add_response = self.execute_request(
            "PATCH",
            f"api/v2/policy/urllist/{args.url_list_id}/append",
            json=add_payload
        )

        # Deploy the changes
        deploy_response = self.execute_request(
            "POST",
            "api/v2/policy/urllist/deploy"
        )

        return {
            "add_result": add_response,
            "deploy_result": deploy_response,
            "message": f"Successfully added {len(args.items)} item(s) to blocklist"
        }