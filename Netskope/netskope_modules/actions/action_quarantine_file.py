from pydantic import Field

from netskope_modules.actions.action_base import NetskopeAction, NetskopeActionArguments


class QuarantineFileArguments(NetskopeActionArguments):
    file_id: str = Field(..., description="The SaaS file identifier")


class QuarantineFileAction(NetskopeAction):
    """
    Quarantine a SaaS file using Netskope remediation.
    """

    def run(self, arguments: dict) -> None:
        args = QuarantineFileArguments(**arguments)
        self.initialize_action_arguments(args)

        self.execute_request(
            "POST",
            "api/v2/infrastructure/remediation/quarantine",
            json={"file_id": args.file_id},
        )

        self.log(level="info", message=f'Successfully quarantined file "{args.file_id}"')
