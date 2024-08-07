"""
Models for EDR Alerts attributes.

https://developer.manage.trellix.com/mvision/apis/threats

Since some version, alert attributes contains different format.
For backward compatibility, we need to handle both formats.
"""

from typing import Any

from pydantic import BaseModel


class EdrAlertAttributes(BaseModel):
    """Alert Attributes."""

    traceId: str
    parentTraceId: str
    rootTraceId: str | None = None
    aGuid: str
    detectionDate: str
    eventDate: str | None = None
    eventType: str
    severity: str | None = None
    score: int | None = None
    detectionTags: list[str] | None = None
    relatedTraceIds: list[str] | None = None
    ruleId: str | None = None
    rank: int | None = None
    pid: int | None = None
    version: str | None = None
    parentsTraceId: list[str] | None = None
    processName: str | None = None
    user: str | None = None
    cmdLine: str | None = None
    hashId: str | None = None
    h_os: str | None = None
    domain: str | None = None
    hostName: str | None = None

    @staticmethod
    def parse_response(json: dict[str, Any]) -> "EdrAlertAttributes":
        """
        Parse the response.

        Args:
            json: dict[str, str]

        Returns:
            EdrAlertAttributes
        """
        return EdrAlertAttributes(
            traceId=json.get("Trace_Id"),
            parentTraceId=json.get("Parent_Trace_Id"),
            rootTraceId=json.get("Root_Trace_Id"),
            aGuid=json.get("MAGUID"),
            detectionDate=json.get("DetectionDate"),
            eventDate=json.get("Event_Date"),
            # api docs does not have this field, and seems like we do not parse it in format
            # but for backward compatibility `eventType` by default is set to `alert`
            eventType=json.get("Event_Type") or "alert",
            severity=json.get("Severity"),
            score=json.get("Score"),
            detectionTags=json.get("Detection_Tags"),
            relatedTraceIds=json.get("Related_Trace_Id"),
            ruleId=json.get("RuleId"),
            rank=json.get("Rank"),
            pid=json.get("Pid"),
            version=json.get("Version"),
            parentsTraceId=json.get("Parents_Trace_Id"),
            processName=json.get("ProcessName"),
            cmdLine=json.get("CommandLine"),
            hashId=json.get("Hash_Id"),
            h_os=json.get("Host_OS"),
            hostName=json.get("Host_Name"),
            # Api docs does not have these fields in separate keys, however `User` in new version contains:
            #  - `domain`
            #  - `Name`
            # So we split it into two fields: `user` and `domain`
            user=json.get("User", {}).get("name"),
            domain=json.get("User", {}).get("domain"),
        )
