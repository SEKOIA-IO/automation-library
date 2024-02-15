from datetime import datetime
from typing import Optional

from management.mgmtsdk_v2.entities.deep_visibility_v2 import DvQuery
from pydantic import BaseModel, Field
from tenacity import (
    Retrying,
    retry_if_not_exception_type,
    stop_after_delay,
    wait_exponential,
)

from sentinelone_module.base import SentinelOneAction
from sentinelone_module.exceptions import (
    QueryDeepVisibilityCanceledError,
    QueryDeepVisibilityError,
    QueryDeepVisibilityFailedError,
    QueryDeepVisibilityRunningError,
    QueryDeepVisibilityTimeoutError,
)
from sentinelone_module.helpers import to_rfc3339


class QueryDeepVisibilityArguments(BaseModel):
    group_ids: list[str] | None
    site_ids: list[str] | None
    query: str
    from_date: datetime
    to_date: datetime
    timeout: int = Field(
        ...,
        description="The maximum time, in seconds, the query should be processed in",
    )

    def to_query(self) -> DvQuery:
        params = {
            "query": self.query,
            "fromDate": to_rfc3339(self.from_date),
            "toDate": to_rfc3339(self.to_date),
        }

        if self.site_ids:
            params["siteIds"] = self.site_ids

        if self.group_ids:
            params["groupIds"] = self.group_ids

        return DvQuery(**params)


class DeepVisibilityEvent(BaseModel):
    agentDomain: str | None = None
    agentGroupId: str | None = None
    agentId: str | None = None
    agentInfected: bool | None = None
    agentIp: str | None = None
    agentIsActive: bool | None = None
    agentIsDecommissioned: bool | None = None
    agentMachineType: str | None = None
    agentName: str | None = None
    agentNetworkStatus: str | None = None
    agentOs: str | None = None
    agentUuid: str | None = None
    agentVersion: str | None = None
    createdAt: str | None = None
    id: str | None = None
    objectType: str | None = None
    processName: str | None = None
    siteName: str | None = None
    user: str | None = None
    connectionStatus: Optional[str]
    direction: Optional[str]
    dnsRequest: Optional[str]
    dnsResponse: Optional[str]
    dstIp: Optional[str]
    dstPort: Optional[str]
    eventType: Optional[str]
    fileFullName: Optional[str]
    fileId: Optional[str]
    fileMd5: Optional[str]
    fileSha1: Optional[str]
    fileSha256: Optional[str]
    fileSize: Optional[str]
    fileType: Optional[str]
    forensicUrl: Optional[str]
    indicatorCategory: Optional[str]
    indicatorDescription: Optional[str]
    indicatorMetadata: Optional[str]
    indicatorName: Optional[str]
    isAgentVersionFullySupportedForPg: Optional[bool]
    isAgentVersionFullySupportedForPgMessage: Optional[str]
    loginsBaseType: Optional[str]
    loginsUserName: Optional[str]
    md5: Optional[str]
    networkMethod: Optional[str]
    networkSource: Optional[str]
    networkUrl: Optional[str]
    oldFileMd5: Optional[str]
    oldFileName: Optional[str]
    oldFileSha1: Optional[str]
    oldFileSha256: Optional[str]
    parentPid: Optional[str]
    parentProcessGroupId: Optional[str]
    parentProcessIsMalicious: Optional[bool]
    parentProcessName: Optional[str]
    parentProcessStartTime: Optional[str]
    parentProcessUniqueKey: Optional[str]
    pid: Optional[str]
    processCmd: Optional[str]
    processDisplayName: Optional[str]
    processGroupId: Optional[str]
    processImagePath: Optional[str]
    processImageSha1Hash: Optional[str]
    processIntegrityLevel: Optional[str]
    processIsMalicious: Optional[bool]
    processIsRedirectedCommandProcessor: Optional[str]
    processIsWow64: Optional[str]
    processRoot: Optional[str]
    processSessionId: Optional[str]
    processStartTime: Optional[str]
    processSubSystem: Optional[str]
    processUniqueKey: Optional[str]
    processUserName: Optional[str]
    publisher: Optional[str]
    registryId: Optional[str]
    registryPath: Optional[str]
    relatedToThreat: Optional[str]
    rpid: Optional[str]
    sha1: Optional[str]
    sha256: Optional[str]
    signatureSignedInvalidReason: Optional[str]
    signedStatus: Optional[str]
    srcIp: Optional[str]
    srcPort: Optional[int]
    srcProcDownloadToken: Optional[str]
    taskName: Optional[str]
    taskPath: Optional[str]
    threatStatus: Optional[str]
    tid: Optional[str]
    trueContext: Optional[str]
    verifiedStatus: Optional[str]


class DeepVisibilityEvents(BaseModel):
    status: str
    status_reason: str
    events: list[DeepVisibilityEvent]


IN_PROGRESS_QUERY_STATUSES = {
    "RUNNING",
    "EVENTS_RUNNING",
    "QUERY_RUNNING",
    "PROCESS_RUNNING",
}
FINALIZED_QUERY_STATUSES = {"EMPTY_RESULTS", "FINISHED"}
CANCELED_QUERY_STATUSES = {"QUERY_CANCEL", "QUERY_EXPIRED", "TIMEOUT"}
FAILED_QUERY_STATUSES = {"QUERY_NOT_FOUND", "FAILED", "FAILED_CLIENT"}


class QueryDeepVisibilityAction(SentinelOneAction):
    name = "Query events in Deep Visibility"
    description = "Create a query in Deep Visibility and get the events"
    results_model = DeepVisibilityEvents

    def _wait_for_completion(self, query_id: str, timeout: int) -> None:
        try:
            for attempt in Retrying(
                stop=stop_after_delay(timeout),
                wait=wait_exponential(multiplier=1, min=1, max=10),
                reraise=True,
                retry=retry_if_not_exception_type((QueryDeepVisibilityCanceledError, QueryDeepVisibilityFailedError)),
            ):
                with attempt:
                    result = self.client.deep_visibility_v2.get_query_status(query_id)

                    if result.data.responseState in FINALIZED_QUERY_STATUSES:
                        return
                    elif result.data.responseState in IN_PROGRESS_QUERY_STATUSES:
                        raise QueryDeepVisibilityRunningError(f"status {result.data.responseState}")
                    elif result.data.responseState in CANCELED_QUERY_STATUSES:
                        raise QueryDeepVisibilityCanceledError(result.json["data"].get("responseError"))
                    elif result.data.responseState in FAILED_QUERY_STATUSES:
                        raise QueryDeepVisibilityFailedError(result.json["data"].get("responseError"))
        except QueryDeepVisibilityRunningError:
            raise QueryDeepVisibilityTimeoutError(timeout)

    def run(self, arguments: QueryDeepVisibilityArguments):
        result = self.client.deep_visibility_v2.create_query(arguments.to_query())
        try:
            self._wait_for_completion(result.data, arguments.timeout)
        except QueryDeepVisibilityError as error:
            return {"status": error.status, "status_reason": str(error), "events": []}
        result = self.client.deep_visibility_v2.get_all_events(queryId=result.data)
        print(result)
        return {
            "status": "succeed",
            "status_reason": "The query was successfully executed",
            "events": result.json["data"],
        }
