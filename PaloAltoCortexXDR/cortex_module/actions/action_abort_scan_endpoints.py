from enum import Enum
from typing import Any

from pydantic.main import BaseModel

from PaloAltoCortexXDR.cortex_module.actions import PaloAltoCortexXDRAction


class PlatformEnum(Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    ANDROID = "android"


class IsolateEnum(Enum):
    ISOLATED = "isolated"
    UNISOLATED = "unisolated"


class ScanStatusEnum(Enum):
    NONE = "none"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CANCELED = "canceled"
    ABORTED = "aborted"
    PENDING_CANCELLATION = "pending_cancellation"
    SUCCESS = "success"
    ERROR = "error"


class AbortScanEndpointsArguments(BaseModel):
    """
    Arguments for the scan endpoints action.
    """

    incident_id: str | None = None

    # filters
    filter_endpoint_id_list: list[str] | None = None
    filter_dist_name: list[str] | None = None
    filter_group_name: list[str] | None = None
    filter_ip_list: list[str] | None = None
    filter_alias: list[str] | None = None
    filter_hostname: list[str] | None = None
    filter_platform: list[PlatformEnum] | None = None
    filter_isolate: list[IsolateEnum] | None = None
    filter_scan_status: list[ScanStatusEnum] | None = None


class AbortScanEndpointsAction(PaloAltoCortexXDRAction):
    """
    This action is used to scan endpoints
    """

    request_uri = "public_api/v1/endpoints/abort_scan"

    def request_payload(self, arguments: dict[str, Any]) -> dict[str, Any]:
        model = AbortScanEndpointsArguments(**arguments)

        result: dict[str, Any] = {"request_data": {}}

        if model.incident_id:
            result["request_data"]["incident_id"] = model.incident_id

        filters = []
        if model.filter_endpoint_id_list:
            filters.append({"field": "endpoint_id_list", "operator": "in", "value": model.filter_endpoint_id_list})

        if model.filter_dist_name:
            filters.append({"field": "dist_name", "operator": "in", "value": model.filter_dist_name})

        if model.filter_group_name:
            filters.append({"field": "group_name", "operator": "in", "value": model.filter_group_name})

        if model.filter_ip_list:
            filters.append({"field": "ip_list", "operator": "in", "value": model.filter_ip_list})

        if model.filter_alias:
            filters.append({"field": "alias", "operator": "in", "value": model.filter_alias})

        if model.filter_hostname:
            filters.append({"field": "hostname", "operator": "in", "value": model.filter_hostname})

        if model.filter_platform:
            filters.append(
                {"field": "platform", "operator": "in", "value": [item.value for item in model.filter_platform]}
            )

        if model.filter_isolate:
            filters.append(
                {"field": "isolate", "operator": "in", "value": [item.value for item in model.filter_isolate]}
            )

        if model.filter_scan_status:
            filters.append(
                {"field": "scan_status", "operator": "in", "value": [item.value for item in model.filter_scan_status]}
            )

        if len(filters) > 0:
            result["request_data"]["filters"] = filters

        else:
            result["request_data"]["filters"] = "all"

        return result
