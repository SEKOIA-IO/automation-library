from typing import Any

from netskope_modules.actions.action_base import NetskopeAction


class NetskopeBlocklistAction(NetskopeAction):
    """
    Common helpers for actions that operate on Netskope blocklists.
    """

    @staticmethod
    def build_blocklist_result(
        *,
        action_name: str,
        api_request: dict[str, Any],
        action_response: Any,
        status: str,
    ) -> dict:
        return {
            "action_name": action_name,
            "action_request": api_request.get("curl", ""),
            "action_response": action_response,
            "action_status": status,
        }
