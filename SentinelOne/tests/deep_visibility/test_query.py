import os
from datetime import UTC, datetime, timedelta

import pytest
import requests_mock

from sentinelone_module.base import SentinelOneConfiguration, SentinelOneModule
from sentinelone_module.deep_visibility.query import QueryDeepVisibilityAction, QueryDeepVisibilityArguments


@pytest.fixture(scope="module")
def arguments():
    return QueryDeepVisibilityArguments(
        site_ids=["1234567890"],
        query="EndpointName exists",
        from_date="2022-07-31T00:00:00Z",
        to_date="2022-08-01T00:00:00Z",
        timeout=1,
    )


def test_query(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    action = QueryDeepVisibilityAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/dv/init-query",
            json={"data": {"queryId": "1234567890"}},
        )
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/dv/query-status?queryId=1234567890",
            json={"data": {"responseState": "FINISHED", "responseError": ""}},
        )
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/dv/events?queryId=1234567890",
            json={
                "data": [
                    {
                        "agentOs": "linux",
                        "srcIp": "string",
                        "rpid": "string",
                        "indicatorMetadata": "string",
                        "tid": "string",
                        "oldFileName": "string",
                        "processIsMalicious": False,
                        "processGroupId": "string",
                        "oldFileSha256": "string",
                        "processImagePath": "string",
                        "processUserName": "string",
                        "taskName": "string",
                        "agentId": "string",
                        "isAgentVersionFullySupportedForPgMessage": "string",
                        "loginsBaseType": "string",
                        "oldFileMd5": "string",
                        "connectionStatus": "string",
                        "parentPid": "string",
                        "parentProcessStartTime": "string",
                        "id": "string",
                        "user": "string",
                        "agentName": "string",
                        "dstPort": 80,
                        "parentProcessGroupId": "string",
                        "networkSource": "string",
                        "trueContext": "string",
                        "fileId": "string",
                        "taskPath": "string",
                        "networkMethod": "string",
                        "pid": "string",
                        "agentUuid": "string",
                        "srcPort": 45089,
                        "fileSha1": "string",
                        "isAgentVersionFullySupportedForPg": False,
                        "fileSize": "string",
                        "processSessionId": "string",
                        "oldFileSha1": "string",
                        "parentProcessIsMalicious": False,
                        "processSubSystem": "string",
                        "signatureSignedInvalidReason": "string",
                        "md5": "string",
                        "processImageSha1Hash": "string",
                        "indicatorName": "string",
                        "threatStatus": "string",
                        "agentMachineType": "string",
                        "registryId": "string",
                        "processDisplayName": "string",
                        "dnsResponse": "string",
                        "agentIsActive": True,
                        "fileFullName": "string",
                        "indicatorDescription": "string",
                        "indicatorCategory": "string",
                        "dstIp": "string",
                        "signedStatus": "string",
                        "processUniqueKey": "string",
                        "srcProcDownloadToken": "string",
                        "fileSha256": "string",
                        "fileType": "string",
                        "processIsWow64": "string",
                        "agentVersion": "string",
                        "processName": "string",
                        "processCmd": "string",
                        "relatedToThreat": "string",
                        "parentProcessUniqueKey": "string",
                        "sha256": "string",
                        "agentIsDecommissioned": False,
                        "forensicUrl": "string",
                        "eventType": "string",
                        "loginsUserName": "string",
                        "processIntegrityLevel": "string",
                        "direction": "string",
                        "agentIp": "string",
                        "processIsRedirectedCommandProcessor": "string",
                        "objectType": "string",
                        "processRoot": "string",
                        "agentInfected": False,
                        "registryPath": "string",
                        "fileMd5": "string",
                        "processStartTime": "string",
                        "siteName": "string",
                        "agentDomain": "string",
                        "createdAt": "2018-02-27T04:49:26.257525Z",
                        "parentProcessName": "string",
                        "verifiedStatus": "string",
                        "dnsRequest": "string",
                        "agentGroupId": "string",
                        "agentNetworkStatus": "string",
                        "networkUrl": "string",
                        "publisher": "string",
                        "sha1": "string",
                    }
                ],
                "pagination": {
                    "nextCursor": "YWdlbnRfaWQ6NTgwMjkzODE=",
                    "totalItems": 1,
                },
            },
        )
        result = action.run(arguments)

        assert result["status"] == "succeed"
        assert len(result["events"]) > 0


def test_query_failed(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    action = QueryDeepVisibilityAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/dv/init-query",
            json={"data": {"queryId": "1234567890"}},
        )
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/dv/query-status?queryId=1234567890",
            json={"data": {"responseState": "FAILED", "responseError": ""}},
        )
        result = action.run(arguments)

        assert result["status"] == "failed"


def test_query_canceled(symphony_storage, sentinelone_hostname, sentinelone_module, arguments):
    action = QueryDeepVisibilityAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/dv/init-query",
            json={"data": {"queryId": "1234567890"}},
        )
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/dv/query-status?queryId=1234567890",
            json={"data": {"responseState": "QUERY_CANCEL", "responseError": ""}},
        )
        result = action.run(arguments)

        assert result["status"] == "canceled"


def test_query_exhausted_retries(symphony_storage, sentinelone_hostname, sentinelone_module):
    arguments = QueryDeepVisibilityArguments(
        site_ids=["1234567890"],
        query="EndpointName exists",
        from_date="2022-07-31T00:00:00Z",
        to_date="2022-08-01T00:00:00Z",
        timeout=1,
    )
    action = QueryDeepVisibilityAction(module=sentinelone_module, data_path=symphony_storage)

    with requests_mock.Mocker() as mock:
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/system/status",
            json={"data": {"health": "ok"}},
        )
        mock.post(
            f"https://{sentinelone_hostname}/web/api/v2.1/dv/init-query",
            json={"data": {"queryId": "1234567890"}},
        )
        mock.get(
            f"https://{sentinelone_hostname}/web/api/v2.1/dv/query-status?queryId=1234567890",
            json={"data": {"responseState": "RUNNING", "responseError": ""}},
        )
        result = action.run(arguments)

        assert result["status"] == "timeout"


@pytest.mark.skipif(
    "{'SENTINELONE_HOSTNAME', 'SENTINELONE_API_TOKEN', 'SENTINELONE_SITE_ID'}.issubset(os.environ.keys()) == False"
)
def test_list_remote_scripts_integration(symphony_storage):
    module = SentinelOneModule()
    module.configuration = SentinelOneConfiguration(
        hostname=os.environ["SENTINELONE_HOSTNAME"],
        api_token=os.environ["SENTINELONE_API_TOKEN"],
    )
    now = datetime.now(UTC)
    arguments = QueryDeepVisibilityArguments(
        site_ids=[os.environ["SENTINELONE_SITE_ID"]],
        query="EndpointName exists",
        from_date=(now - timedelta(days=1)),
        to_date=(now - timedelta(minutes=1)),
        timeout=120,
    )

    action = QueryDeepVisibilityAction(module=module, data_path=symphony_storage)
    result = action.run(arguments)
    assert result is not None
    assert result["status"] == "succeed"
