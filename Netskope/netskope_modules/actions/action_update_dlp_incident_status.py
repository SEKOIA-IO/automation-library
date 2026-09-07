from pydantic import Field

from netskope_modules.actions.action_base import NetskopeAction, NetskopeActionArguments


class UpdateDlpIncidentStatusArguments(NetskopeActionArguments):
    incident_id: str = Field(..., description="The Netskope DLP incident identifier")
    status: str = Field(..., description="The new DLP incident status")
    notes: str | None = Field(None, description="Optional remediation notes")


class UpdateDlpIncidentStatusAction(NetskopeAction):
    """
    Update the status of a Netskope DLP incident.
    """

    def run(self, arguments: dict) -> None:
        args = UpdateDlpIncidentStatusArguments(**arguments)
        self.initialize_action_arguments(args)

        payload = {"status": args.status}
        if args.notes:
            payload["notes"] = args.notes

        self.execute_request("PATCH", f"api/v2/dlp/incident/{args.incident_id}", json=payload)

        self.log(
            level="info",
            message=f'Successfully updated DLP incident "{args.incident_id}" to "{args.status}"',
        )
