from datetime import datetime

from management.mgmtsdk_v2.entities.deep_visibility_v2 import DvQuery
from pydantic import BaseModel, Field
from tenacity import Retrying, stop_after_delay, wait_exponential

from sentinelone_module.base import SentinelOneAction
from sentinelone_module.exceptions import (
    QueryDeepVisibilityCanceledError,
    QueryDeepVisibilityError,
    QueryDeepVisibilityFailedError,
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
    agentOs: str
    srcIp: str
    rpid: str
    indicatorMetadata: str
    tid: str
    oldFileName: str
    processIsMalicious: bool
    processGroupId: str
    oldFileSha256: str
    processImagePath: str
    processUserName: str
    taskName: str
    agentId: str
    isAgentVersionFullySupportedForPgMessage: str
    loginsBaseType: str
    oldFileMd5: str
    connectionStatus: str
    parentPid: str
    parentProcessStartTime: str
    id: str
    user: str
    agentName: str
    dstPort: int
    parentProcessGroupId: str
    networkSource: str
    trueContext: str
    fileId: str
    taskPath: str
    networkMethod: str
    pid: str
    agentUuid: str
    srcPort: int
    fileSha1: str
    isAgentVersionFullySupportedForPg: bool
    fileSize: str
    processSessionId: str
    oldFileSha1: str
    parentProcessIsMalicious: bool
    processSubSystem: str
    signatureSignedInvalidReason: str
    md5: str
    processImageSha1Hash: str
    indicatorName: str
    threatStatus: str
    agentMachineType: str
    registryId: str
    processDisplayName: str
    dnsResponse: str
    agentIsActive: bool
    fileFullName: str
    indicatorDescription: str
    indicatorCategory: str
    dstIp: str
    signedStatus: str
    processUniqueKey: str
    srcProcDownloadToken: str
    fileSha256: str
    fileType: str
    processIsWow64: str
    agentVersion: str
    processName: str
    processCmd: str
    relatedToThreat: str
    parentProcessUniqueKey: str
    sha256: str
    agentIsDecommissioned: bool
    forensicUrl: str
    eventType: str
    loginsUserName: str
    processIntegrityLevel: str
    direction: str
    agentIp: str
    processIsRedirectedCommandProcessor: str
    objectType: str
    processRoot: str
    agentInfected: bool
    registryPath: str
    fileMd5: str
    processStartTime: str
    siteName: str
    agentDomain: str
    createdAt: datetime
    parentProcessName: str
    verifiedStatus: str
    dnsRequest: str
    agentGroupId: str
    agentNetworkStatus: str
    networkUrl: str
    publisher: str
    sha1: str


class DeepVisibilityEvents(BaseModel):
    status: str
    status_reason: str
    events: list[DeepVisibilityEvent]


FINALIZED_QUERY_STATUSES = {"EMPTY_RESULTS", "FINISHED"}
CANCELED_QUERY_STATUSES = {"QUERY_CANCEL", "QUERY_EXPIRED", "TIMEOUT"}
FAILED_QUERY_STATUSES = {"QUERY_NOT_FOUND", "FAILED", "FAILED_CLIENT"}


class QueryDeepVisibilityAction(SentinelOneAction):
    name = "Query events in Deep Visibility"
    description = "Create a query in Deep Visibility and get the events"
    results_model = DeepVisibilityEvents

    def _wait_for_completion(self, query_id: str, timeout: int) -> None:
        for attempt in Retrying(
            stop=stop_after_delay(timeout),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
        ):
            with attempt:
                result = self.client.deep_visibility_v2.get_query_status(query_id)

                if result.data.responseState in FINALIZED_QUERY_STATUSES:
                    return
                elif result.data.responseState in CANCELED_QUERY_STATUSES:
                    raise QueryDeepVisibilityCanceledError(result.json["data"].get("responseError"))
                elif result.data.responseState in FAILED_QUERY_STATUSES:
                    raise QueryDeepVisibilityFailedError(result.json["data"].get("responseError"))

        raise QueryDeepVisibilityTimeoutError(timeout)

    def run(self, arguments: QueryDeepVisibilityArguments):
        result = self.client.deep_visibility_v2.create_query(arguments.to_query())

        try:
            self._wait_for_completion(result.data, arguments.timeout)
        except QueryDeepVisibilityError as error:
            return {"status": error.status, "status_reason": str(error), "events": []}

        result = self.client.deep_visibility_v2.get_all_events(queryId=result.data)
        return {
            "status": "succeed",
            "status_reason": "The query was successfully executed",
            "events": result.json["data"],
        }
