from datetime import datetime

from management.mgmtsdk_v2.entities.deep_visibility_v2 import DvQuery
from pydantic import BaseModel, ConfigDict, Field
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
    group_ids: list[str] | None = None
    site_ids: list[str] | None = None
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
    # The Deep Visibility API returns numbers for some of these string fields (ports, pids,
    # sizes); Pydantic v1 coerced them silently, v2 needs to be told to.
    model_config = ConfigDict(coerce_numbers_to_str=True)

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
    connectionStatus: str | None = None
    direction: str | None = None
    dnsRequest: str | None = None
    dnsResponse: str | None = None
    dstIp: str | None = None
    dstPort: str | None = None
    eventType: str | None = None
    fileFullName: str | None = None
    fileId: str | None = None
    fileMd5: str | None = None
    fileSha1: str | None = None
    fileSha256: str | None = None
    fileSize: str | None = None
    fileType: str | None = None
    forensicUrl: str | None = None
    indicatorCategory: str | None = None
    indicatorDescription: str | None = None
    indicatorMetadata: str | None = None
    indicatorName: str | None = None
    isAgentVersionFullySupportedForPg: bool | None = None
    isAgentVersionFullySupportedForPgMessage: str | None = None
    loginsBaseType: str | None = None
    loginsUserName: str | None = None
    md5: str | None = None
    networkMethod: str | None = None
    networkSource: str | None = None
    networkUrl: str | None = None
    oldFileMd5: str | None = None
    oldFileName: str | None = None
    oldFileSha1: str | None = None
    oldFileSha256: str | None = None
    parentPid: str | None = None
    parentProcessGroupId: str | None = None
    parentProcessIsMalicious: bool | None = None
    parentProcessName: str | None = None
    parentProcessStartTime: str | None = None
    parentProcessUniqueKey: str | None = None
    pid: str | None = None
    processCmd: str | None = None
    processDisplayName: str | None = None
    processGroupId: str | None = None
    processImagePath: str | None = None
    processImageSha1Hash: str | None = None
    processIntegrityLevel: str | None = None
    processIsMalicious: bool | None = None
    processIsRedirectedCommandProcessor: str | None = None
    processIsWow64: str | None = None
    processRoot: str | None = None
    processSessionId: str | None = None
    processStartTime: str | None = None
    processSubSystem: str | None = None
    processUniqueKey: str | None = None
    processUserName: str | None = None
    publisher: str | None = None
    registryId: str | None = None
    registryPath: str | None = None
    relatedToThreat: str | None = None
    rpid: str | None = None
    sha1: str | None = None
    sha256: str | None = None
    signatureSignedInvalidReason: str | None = None
    signedStatus: str | None = None
    srcIp: str | None = None
    srcPort: int | None = None
    srcProcDownloadToken: str | None = None
    taskName: str | None = None
    taskPath: str | None = None
    threatStatus: str | None = None
    tid: str | None = None
    trueContext: str | None = None
    verifiedStatus: str | None = None


class DeepVisibilityEvents(BaseModel):
    status: str | None = None
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
