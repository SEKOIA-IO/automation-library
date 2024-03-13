from datetime import datetime

from management.mgmtsdk_v2.entities.deep_visibility_v2 import DvQuery
from pydantic import BaseModel, Field
from tenacity import Retrying, retry_if_not_exception_type, stop_after_delay, wait_exponential

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
    connectionStatus: str | None
    direction: str | None
    dnsRequest: str | None
    dnsResponse: str | None
    dstIp: str | None
    dstPort: str | None
    eventType: str | None
    fileFullName: str | None
    fileId: str | None
    fileMd5: str | None
    fileSha1: str | None
    fileSha256: str | None
    fileSize: str | None
    fileType: str | None
    forensicUrl: str | None
    indicatorCategory: str | None
    indicatorDescription: str | None
    indicatorMetadata: str | None
    indicatorName: str | None
    isAgentVersionFullySupportedForPg: bool | None
    isAgentVersionFullySupportedForPgMessage: str | None
    loginsBaseType: str | None
    loginsUserName: str | None
    md5: str | None
    networkMethod: str | None
    networkSource: str | None
    networkUrl: str | None
    oldFileMd5: str | None
    oldFileName: str | None
    oldFileSha1: str | None
    oldFileSha256: str | None
    parentPid: str | None
    parentProcessGroupId: str | None
    parentProcessIsMalicious: bool | None
    parentProcessName: str | None
    parentProcessStartTime: str | None
    parentProcessUniqueKey: str | None
    pid: str | None
    processCmd: str | None
    processDisplayName: str | None
    processGroupId: str | None
    processImagePath: str | None
    processImageSha1Hash: str | None
    processIntegrityLevel: str | None
    processIsMalicious: bool | None
    processIsRedirectedCommandProcessor: str | None
    processIsWow64: str | None
    processRoot: str | None
    processSessionId: str | None
    processStartTime: str | None
    processSubSystem: str | None
    processUniqueKey: str | None
    processUserName: str | None
    publisher: str | None
    registryId: str | None
    registryPath: str | None
    relatedToThreat: str | None
    rpid: str | None
    sha1: str | None
    sha256: str | None
    signatureSignedInvalidReason: str | None
    signedStatus: str | None
    srcIp: str | None
    srcPort: int | None
    srcProcDownloadToken: str | None
    taskName: str | None
    taskPath: str | None
    threatStatus: str | None
    tid: str | None
    trueContext: str | None
    verifiedStatus: str | None


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
            return DeepVisibilityEvents(status=error.status, status_reason=str(error), events=[]).dict(
                exclude_none=True
            )
        result = self.client.deep_visibility_v2.get_all_events(queryId=result.data)
        return DeepVisibilityEvents(
            status="succeed",
            status_reason="The query was successfully executed",
            events=result.json["data"],
        ).dict(exclude_none=True)
