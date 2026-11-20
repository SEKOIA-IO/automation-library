"""Move one Graph message and independently verify its destination."""

from typing import Any

from pydantic import BaseModel, ConfigDict

from .action_base import MicrosoftGraphActionBase
from .errors import VerificationError, describe_error
from .graph import MailGraph


class MoveMessageArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user: str
    message_id: str | dict[str, Any]
    destination_folder: str


class MoveMessageAction(MicrosoftGraphActionBase):
    may_modify_data = True

    def run(self, arguments: Any) -> dict[str, Any]:
        args = MoveMessageArguments.model_validate(arguments)
        graph = MailGraph(self.client)
        message_id = self._resolve_message_id(args.message_id)
        try:
            destination = graph.folder(args.user, args.destination_folder)
        except Exception as exc:
            return self.report_item_errors({}, [describe_error(exc)], "failed")
        result: dict[str, Any] = {
            "user": args.user,
            "original_message_id": message_id,
            "message_id": None,
            "destination_folder_id": destination["id"],
            "destination_folder_name": destination["displayName"],
            "parent_folder_id": None,
            "execution_status": "failed_or_unknown",
            "verification_status": "not_performed",
            "errors": [],
        }
        details = []
        outcome = "succeeded"
        try:
            # POST is not automatically retried: a timeout may occur after the move succeeded.
            moved = graph.json(
                "POST", f"{graph.message_url(args.user, message_id)}/move", json={"destinationId": destination["id"]}
            )
            result.update(execution_status="succeeded", verification_status="unknown", message_id=moved.get("id"))
            if not result["message_id"]:
                raise VerificationError(
                    "Graph accepted the move but returned no message ID. Verify its location before retrying."
                )
            current = graph.json(
                "GET",
                graph.message_url(args.user, result["message_id"]),
                params={"$select": "id,parentFolderId,internetMessageId"},
            )
            result["parent_folder_id"] = current.get("parentFolderId")
            result["verification_status"] = (
                "verified" if result["parent_folder_id"] == destination["id"] else "mismatch"
            )
            if result["verification_status"] == "mismatch":
                outcome = "partial"
                details.append(
                    describe_error(
                        VerificationError(
                            "Move was accepted but the destination does not match. Verify the message before retrying."
                        ),
                        may_modify=True,
                    )
                )
        except Exception as exc:
            detail = describe_error(exc, may_modify=True)
            if result["execution_status"] == "succeeded":
                detail["outcome_unknown"] = True
            details.append(detail)
            outcome = "unknown" if detail["outcome_unknown"] else "failed"
        result["errors"] = [detail["message"] for detail in details]
        return self.report_item_errors(result, details, outcome)
