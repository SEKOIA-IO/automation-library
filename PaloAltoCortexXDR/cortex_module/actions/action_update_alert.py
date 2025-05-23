from abc import ABC
from enum import Enum
from typing import Any

from pydantic.main import BaseModel

from cortex_module.actions import ArgumentsT, PaloAltoCortexXDRAction


class Status(Enum):
    NEW = "new"
    UNDER_INVESTIGATION = "under_investigation"
    RESOLVED_SECURITY_TESTING = "resolved_security_testing"
    RESOLVED_KNOWN_ISSUE = "resolved_known_issue"
    RESOLVED_DUPLICATE = "resolved_duplicate"
    RESOLVED_OTHER = "resolved_other"
    RESOLVED_FALSE_POSITIVE = "resolved_false_positive"
    RESOLVED_TRUE_POSITIVE = "resolved_true_positive"


class Severity(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class UpdateAlertArguments(BaseModel):
    """
    Arguments for the update alert action.
    """

    alert_id_list: list[str]
    severity: Severity
    status: Status


class UpdateAlertAction(PaloAltoCortexXDRAction[UpdateAlertArguments]):
    """
    This action is used to update alert.
    """

    request_uri = "public_api/v1/alerts/update_alerts"

    def request_payload(self, arguments: UpdateAlertArguments) -> dict[str, Any]:
        """
        Build the request payload for the action.

        Example of payload:
        {
          "request_data": {
            "alert_id_list": [
              "<list of alert IDs>"
            ],
            "update_data": {
              "severity": "low",
              "status": "resolved_other"
            }
          }
        }

        Args:
            arguments: The arguments passed to the action.

        Returns:
            dict[str, Any]: The request payload.
        """
        return {
            "request_data": {
                "alert_id_list": arguments.alert_id_list,
                "update_data": {"severity": arguments.severity.value, "status": arguments.status.value},
            }
        }
