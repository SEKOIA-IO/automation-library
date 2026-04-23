from pydantic import BaseModel, Field

from netskope_modules.actions.action_base import NetskopeAction


class DeleteBlocklistArguments(BaseModel):
    id: int = Field(..., description="ID of the URL list")


class DeleteBlocklistAction(NetskopeAction):
    """
    Mark a Netskope URL list as pending deletion and deploy the change.
    """

    def run(self, arguments: dict) -> dict:
        args = DeleteBlocklistArguments(**arguments)

        delete_response = self.execute_request("DELETE", f"api/v2/policy/urllist/{args.id}")

        # Deploy the deletion
        deploy_response = self.deploy_blocklist_changes()

        return {
            "delete_result": delete_response,
            "deploy_result": deploy_response,
            "message": f"Successfully deleted blocklist {args.id}",
        }
