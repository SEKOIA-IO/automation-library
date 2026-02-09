from unittest.mock import MagicMock, patch

import httpx
import pytest
from respx import MockRouter

from ubika_modules import UbikaModule
from ubika_modules.client.auth import AuthorizationError, AuthorizationTimeoutError
from ubika_modules.connector_ubika_cloud_protector_next_gen import UbikaCloudProtectorNextGenConnector


@pytest.fixture
def trigger(data_storage):
    module = UbikaModule()
    trigger = UbikaCloudProtectorNextGenConnector(module=module, data_path=data_storage)
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger.push_events_to_intakes = MagicMock()
    trigger.configuration = {
        "namespace": "sekoia",
        "refresh_token": "some_token_here",
        "intake_key": "intake_key",
        "chunk_size": 100,
    }
    yield trigger


@pytest.fixture
def message1():
    return {
        "apiVersion": "logs.ubika.io/v1beta",
        "kind": "SecurityEvents",
        "metadata": {"name": "", "namespace": "", "created": None, "updated": None, "version": "0"},
        "spec": {
            "items": [
                {
                    "logAlertUid": "098f6bcd4621d373cade4e832627b4f6",
                    "timestamp": "1747326567848",
                    "request": {
                        "uid": "abcdef",
                        "body": "",
                        "hostname": "ubika.integration.sekoia.cloud",
                        "method": "GET",
                        "path": "/api/.env",
                        "headers": [
                            {"key": "x-request-id", "value": "4d1c331e-14af-4ce1-97a8-99c495ff6b18"},
                            {"key": "x-real-ip", "value": "176.98.186.48"},
                            {"key": "x-ubika-data", "value": "1"},
                            {"key": "host", "value": "ubika.integration.sekoia.cloud"},
                            {"key": "accept", "value": "*/*"},
                            {"key": "accept-encoding", "value": "gzip, deflate"},
                            {
                                "key": "user-agent",
                                "value": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3",
                            },
                        ],
                        "cookies": [],
                        "ipSource": "1.2.3.4",
                        "query": "",
                    },
                    "context": {"assetName": "testAsset", "assetNamespace": "sekoia", "reaction": "BLOCKED"},
                    "uid": "5a105e8b9d40e1329780d62ea2265d8a",
                    "tokens": {
                        "openapi3Name": "",
                        "openapi3Uid": "",
                        "openapi3ErrorType": "",
                        "openapi3ErrorDetails": "",
                        "part": "Multiple",
                        "reason": "ICX Engine: Path Traversal in Path",
                        "customMessage": "",
                        "engineUid": "icxEngine",
                        "engineName": "ICX Engine",
                        "matchingParts": [
                            {
                                "part": "Path",
                                "partKey": "",
                                "partKeyOperator": "",
                                "partKeyPattern": "",
                                "partKeyPatternUid": "",
                                "partKeyPatternName": "",
                                "partKeyPatternVersion": "",
                                "partKeyMatch": "",
                                "partValue": "/api/.env",
                                "partValuePattern": "",
                                "partValueOperator": "pattern",
                                "partValuePatternUid": "PathTraversalOnUriProprietaryPattern_PToU-00740-3.45.1",
                                "partValuePatternName": "Path transversal on URI",
                                "partValuePatternVersion": "PToU-00740-3.45.1",
                                "partValueMatch": "/.env",
                                "scoringlistRuleId": "",
                                "scoringlistRuleWeight": 0,
                            }
                        ],
                        "attackFamily": "Path Traversal",
                        "icxPolicyUid": "default_3.47.0",
                        "icxRuleName": "Path transversal",
                        "icxRuleUid": "abcdef12345",
                        "websocketOpcode": "",
                        "websocketFrom": "",
                        "canonSearchType": "",
                        "eaPolicyUid": "",
                        "eaPolicyName": "",
                        "eaStaticPolicyUid": "",
                        "eaRuleId": "",
                        "eaRuleName": "",
                        "eaTotalScore": 0,
                    },
                }
            ],
            "nextPageToken": "token123",
        },
    }


@pytest.fixture
def message2():
    return {
        "apiVersion": "logs.ubika.io/v1beta",
        "kind": "SecurityEvents",
        "metadata": {"name": "", "namespace": "", "created": None, "updated": None, "version": "0"},
        "spec": {"items": [], "nextPageToken": "tokenEnd"},
    }


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_fetch_events_with_pagination(respx_mock: MockRouter, trigger, message1, message2):
    with patch("ubika_modules.connector_ubika_cloud_protector_base.time") as mock_time:
        mock_time.sleep = MagicMock()

        respx_mock.post("/auth/realms/main/protocol/openid-connect/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "foo-token",
                    "token_type": "bearer",
                    "expires_in": 1799,
                },
            )
        )

        respx_mock.get(
            "https://api.ubika.io/rest/logs.ubika.io/v1/ns/sekoia/security-events",
            params={
                "filters.fromDate": "1747326567845",
                "pagination.realtime": "true",
                "pagination.pageSize": "100",
            },
        ).mock(return_value=httpx.Response(200, json=message1))

        respx_mock.get(
            "https://api.ubika.io/rest/logs.ubika.io/v1/ns/sekoia/security-events",
            params={
                "pagination.pageToken": "token123",
                "pagination.pageSize": "100",
                "pagination.realtime": "true",
            },
        ).mock(return_value=httpx.Response(200, json=message2))

        trigger.from_timestamp = 1747326567845
        events = trigger.fetch_events()

        assert list(events) == [message1["spec"]["items"]]


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_next_batch_sleep_until_next_round(respx_mock: MockRouter, trigger, message1, message2):
    with patch("ubika_modules.connector_ubika_cloud_protector_next_gen.time") as mock_time:
        mock_time.sleep = MagicMock()

        respx_mock.post("/auth/realms/main/protocol/openid-connect/token").mock(
            return_value=httpx.Response(
                200,
                json={
                    "access_token": "foo-token",
                    "token_type": "bearer",
                    "expires_in": 1799,
                },
            )
        )

        respx_mock.get(
            "https://api.ubika.io/rest/logs.ubika.io/v1/ns/sekoia/security-events",
            params={
                "filters.fromDate": "1747326567845",
                "pagination.realtime": "true",
                "pagination.pageSize": "100",
            },
        ).mock(return_value=httpx.Response(200, json=message1))

        respx_mock.get(
            "https://api.ubika.io/rest/logs.ubika.io/v1/ns/sekoia/security-events",
            params={
                "pagination.pageToken": "token123",
                "pagination.pageSize": "100",
                "pagination.realtime": "true",
            },
        ).mock(return_value=httpx.Response(200, json=message2))

        trigger.from_timestamp = 1747326567845

        batch_duration = trigger.configuration.frequency + 20
        start_time = 1747326560
        end_time = start_time + batch_duration
        mock_time.time.side_effect = [start_time, end_time, end_time]

        trigger.next_batch()

        assert trigger.push_events_to_intakes.call_count == 1
        assert mock_time.sleep.call_count == 0


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_authorization_http_error_without_retry(respx_mock: MockRouter, trigger):
    route = respx_mock.post("/auth/realms/main/protocol/openid-connect/token")
    route.mock(
        return_value=httpx.Response(
            400,
            json={"error": "invalid_grant", "error_description": "Invalid refresh token"},
        )
    )

    with patch("time.sleep"), pytest.raises(AuthorizationError):
        trigger.next_batch()

    assert route.call_count == 1


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_authorization_http_error_with_retry(respx_mock: MockRouter, trigger):
    route = respx_mock.post("/auth/realms/main/protocol/openid-connect/token")
    route.mock(
        return_value=httpx.Response(
            500,
            json={"error": "some_error", "error_description": "Error worth retrying"},
        )
    )

    with patch("time.sleep"), pytest.raises(AuthorizationError):
        trigger.next_batch()

    assert route.call_count == 5


@pytest.mark.respx(base_url="https://login.ubika.io")
def test_authorization_timeout_error(respx_mock: MockRouter, trigger):
    route = respx_mock.post("/auth/realms/main/protocol/openid-connect/token")
    route.side_effect = httpx.TimeoutException("Timeout")

    with patch("time.sleep"), pytest.raises(AuthorizationTimeoutError):
        trigger.next_batch()

    assert route.call_count == 5
