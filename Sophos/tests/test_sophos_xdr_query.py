import os
from unittest.mock import MagicMock, Mock

import sys
sys.path.append('/Users/zakaryatoufiki/Desktop/Integration_Work/automation-library/Sophos')

import pytest
import requests_mock

from sophos_module.base import SophosModule
from sophos_module.trigger_sophos_xdr_query import SophosXDRQueryTrigger


@pytest.fixture
def trigger(symphony_storage):
    module = SophosModule()
    trigger = SophosXDRQueryTrigger(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "oauth2_authorization_url": "https://id.sophos.com/api/v2/oauth2/token",
        "api_host": "https://api-eu01.central.sophos.com",
        "client_id": "ec3e58df-3b9a-4970-aedc-f9b756f0fd6d",
        "client_secret": "a0a8d805635e46134c06c0388a99c1d43cbd82585a799ab5216463c49e2705f5c4894d817f6c279a2fc043d5ef7972175768",
    }

    trigger.configuration = {
        "tenant_id": "4feff6df-7454-4036-923d-7b2444462416",
        "chunk_size": 1,
        "intake_key": "0123456789",
        "query" : {
                    "adHocQuery": {
                        "template": "SELECT * FROM xdr_ioc_view"
                    }
                }
    }

    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()
    return trigger

def test_getting_results(trigger):
    host = "https://api-eu01.central.sophos.com"
    url = f"{host}/xdr-query/v1/queries/runs"
    url_query_status = f"{host}/xdr-query/v1/queries/runs/7d00cf17-a987-4d07-ac88-93d4df89fa73"
    url_results = f"{host}/xdr-query/v1/queries/runs/7d00cf17-a987-4d07-ac88-93d4df89fa73/results?maxSize=1000&pageSize=7"

    with requests_mock.Mocker() as mock:
        mock.post(
            f"{trigger.module.configuration.oauth2_authorization_url}",
            status_code=200,
            json={
                "access_token": "access_token",
                "refresh_token": "refresh_token",
                "token_type": "bearer",
                "message": "OK",
                "errorCode": "success",
                "expires_in": 3600,
            },
        )

        mock.get(
            f"{trigger.module.configuration.api_host}/whoami/v1",
            status_code=200,
            json={
                "id": "ea106f70-96b1-4851-bd31-e4395ea407d2",
                "idType": "tenant",
                "apiHosts": {
                    "global": "https://api.central.sophos.com",
                    "dataRegion": host,
                },
            },
        )

        # flake8: noqa
        response = {
                        "id": "7d00cf17-a987-4d07-ac88-93d4df89fa73",
                        "createdAt": "2023-06-30T08:14:55.628Z",
                        "createdBy": {
                            "id": "ec3e58df-3b9a-4970-aedc-f9b756f0fd6d",
                            "type": "service",
                            "accountId": "4feff6df-7454-4036-923d-7b2444462416",
                            "accountType": "tenant"
                        },
                        "expiresAt": "2023-06-30T10:14:55.649Z",
                        "result": "notAvailable",
                        "status": "pending",
                        "template": "SELECT * FROM xdr_ioc_view",
                        "from": "2023-06-29T08:14:55.625Z",
                        "to": "2023-06-30T08:14:55.625Z"
                    }
        
        response_query_status ={
                        "id": "7d00cf17-a987-4d07-ac88-93d4df89fa73",
                        "createdAt": "2023-06-30T08:14:55.628Z",
                        "createdBy": {
                            "id": "ec3e58df-3b9a-4970-aedc-f9b756f0fd6d",
                            "type": "service",
                            "accountId": "4feff6df-7454-4036-923d-7b2444462416",
                            "accountType": "tenant"
                        },
                        "expiresAt": "2023-06-30T10:14:56.084Z",
                        "finishedAt": "2023-06-30T08:15:01.252Z",
                        "result": "succeeded",
                        "status": "finished",
                        "template": "SELECT * FROM xdr_ioc_view",
                        "from": "2023-06-29T08:14:55.625Z",
                        "to": "2023-06-30T08:14:55.625Z"
                    }
        
        response_results = {
                    "items": [
                                {
                                    "upload_size": 1033,
                                    "record_identifier": "22648a5236e08f6e7a930f46d1680a9ea11365fed49ae4eb3a6b18366acf8c1c",
                                    "ioc_severity": 4,
                                },
                                {
                                    "upload_size": 1296,
                                    "record_identifier": "ca930c75bfa5992d669463fdd211e9ccf85f1ff6876466704526656e94b84410",
                                    "ioc_severity": 3,
                                },
                                {
                                    "upload_size": 1021,
                                    "record_identifier": "9ed3ca2f862b037abbab3f0d4ba56a8534b4fb37f5ffae1bedcf007c0595a2aa",
                                    "ioc_severity": 4,
                                },
                                {
                                    "upload_size": 1254,
                                    "record_identifier": "e96c524f39ee22d8c42333b853a05993f1998634385a8f6a8c9f1bf8db7d6177",
                                    "ioc_severity": 3,
                                },
                                {
                                    "upload_size": 983,
                                    "record_identifier": "e74f7be8a322b451df13c94a007f22a61a2f7d82236f7ad0fd842632ce31e6b0",
                                    "ioc_severity": 5,
                                },
                                {
                                    "upload_size": 1296,
                                    "record_identifier": "9f64e276598a3b57b98a4185abc1c4a3db9e05725d985a28709c8cd350cf5b9f",
                                    "ioc_severity": 3,
                                },
                                {
                                    "upload_size": 1744,
                                    "record_identifier": "9a59a621cdb463fecd27f734f4b12f912dd16a708d28d6b6119162e1f37aba61",
                                    "ioc_severity": 5,
                                }
                            ],
                            "metadata": {
                                "columns": [
                                    {
                                        "name": "customer_id",
                                        "type": "string"
                                    },
                                    {
                                        "name": "endpoint_id",
                                        "type": "string"
                                    },
                                    {
                                        "name": "ingestion_timestamp",
                                        "type": "timestamp"
                                    },
                                    {
                                        "name": "schema_version",
                                        "type": "string"
                                    },
                                ]
                            },
                            "pages": {
                                "size": 7,
                                "maxSize": 2000,
                                "total": 1,
                                "items": 7
                            }
                    }
        
        # flake8: qa
        mock.post(url, json=response)
        mock.get(url_query_status, json=response_query_status)
        mock.get(url_results, json=response_results)
        trigger.getting_results("7")
        calls = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
        assert len(calls[0]) == 7
