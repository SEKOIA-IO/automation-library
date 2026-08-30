from typing import Literal

from pydantic import Field

from netskope_modules.actions.action_base import NetskopeAction, NetskopeActionArguments


class RestrictFileSharesArguments(NetskopeActionArguments):
    file_id: str = Field(..., description="The SaaS file identifier")
    operation: Literal["unshare", "restrict-access"] = Field(
        "unshare",
        description="The remediation operation to run",
    )


class RestrictFileSharesAction(NetskopeAction):
    """
    Remove public or external sharing from a SaaS file.
    """

    def run(self, arguments: dict) -> None:
        args = RestrictFileSharesArguments(**arguments)
        self.initialize_action_arguments(args)

        endpoint = f"api/v2/infrastructure/remediation/{args.operation}"
        self.execute_request("POST", endpoint, json={"file_id": args.file_id})

        self.log(
            level="info",
            message=f'Successfully applied "{args.operation}" remediation to file "{args.file_id}"',
        )
