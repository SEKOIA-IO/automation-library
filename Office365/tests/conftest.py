import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
from unittest.mock import AsyncMock, Mock

import pytest
from sekoia_automation import constants
from sekoia_automation.storage import get_data_path

from office365.management_api.configuration import Office365Configuration
from office365.management_api.connector import Office365Connector


@pytest.fixture
def symphony_storage():
    # Clear cache so that we get the right DataPath at every initialization
    get_data_path.cache_clear()

    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()
    yield Path(constants.DATA_STORAGE)

    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


@pytest.fixture
def message_trace_api_401() -> str:
    return (
        "<title>401 - Unauthorized: Access is denied due to invalid credentials."
        '</title><body><div id="header"><h1>Server Error</h1></div><div id="content">'
        '<div class="content-container"><fieldset><h2>401 - Unauthorized: '
        "Access is denied due to invalid credentials."
        "</h2><h3>You do not have permission to view this directory"
        " or page using the credentials that you supplied.</h3></fieldset></div></div></body>"
    )


@pytest.fixture
def message_trace_api_403() -> str:
    return '{"ErrorCode":"","Message":"No permission to access the report for the organization ."}'


@pytest.fixture
def message_trace_report() -> dict:
    return {
        "d": {
            "results": [
                {
                    "__metadata": {
                        "id": "https://reports.office365.com/ecp/ReportingWebService/Reporting.svc/MessageTrace(0)",
                        "uri": "https://reports.office365.com/ecp/ReportingWebService/Reporting.svc/MessageTrace(0)",
                        "type": "TenantReporting.MessageTrace",
                    },
                    "Organization": "snewservices.onmicrosoft.com",
                    "MessageId": "<3a273efc-cd65-4335-96ec-5f6934f0fb10@az.uksouth.production.microsoft.com>",
                    "Received": "\\/Date(1658751973240)\\/",
                    "SenderAddress": "azure-noreply@microsoft.com",
                    "RecipientAddress": "foo.bar@own.security",
                    "Subject": "PIM: MessageTrace API service account has the Privileged Role Administrator role",
                    "Status": "GettingStatus",
                    "ToIP": None,
                    "FromIP": "1.1.1.1",
                    "Size": 87680,
                    "MessageTraceId": "3b4fc661-180d-4c2f-60c9-08da6e38dd10",
                    "StartDate": "\\/Date(1658579297628)\\/",
                    "EndDate": "\\/Date(1658752097628)\\/",
                    "Index": 0,
                },
                {
                    "__metadata": {
                        "id": "https://reports.office365.com/ecp/ReportingWebService/Reporting.svc/MessageTrace(1)",
                        "uri": "https://reports.office365.com/ecp/ReportingWebService/Reporting.svc/MessageTrace(1)",
                        "type": "TenantReporting.MessageTrace",
                    },
                    "Organization": "snewservices.onmicrosoft.com",
                    "MessageId": "<baba5a49-dfd1-4ed2-8fc4-7291a03dd549@PR0P264MB1739.FRAP264.PROD.OUTLOOK.COM>",
                    "Received": "\\/Date(1658751972952)\\/",
                    "SenderAddress": "postmaster@own.security",
                    "RecipientAddress": "azure-noreply@microsoft.com",
                    "Subject": "Undeliverable: PIM: MessageTrace API service"
                    " account has the Privileged Role Administrator role",
                    "Status": "Failed",
                    "ToIP": None,
                    "FromIP": None,
                    "Size": 132391,
                    "MessageTraceId": "47a1a53c-7e88-431e-7154-08da6e38dce4",
                    "StartDate": "\\/Date(1658579297628)\\/",
                    "EndDate": "\\/Date(1658752097628)\\/",
                    "Index": 1,
                },
            ]
        }
    }


@pytest.fixture
def trigger_activation() -> datetime:
    return datetime.now(UTC)


@pytest.fixture
def end_time(trigger_activation) -> datetime:
    return trigger_activation


@pytest.fixture
def start_time(trigger_activation) -> datetime:
    return trigger_activation - timedelta(minutes=1)


@pytest.fixture
def client():
    client = Mock()
    client.activate_subscriptions = AsyncMock()
    client.get_subscription_contents = Mock()
    client.list_subscriptions = AsyncMock()
    client.get_content = AsyncMock()
    yield client


@pytest.fixture
def connector(symphony_storage, client, monkeypatch):
    connector = Office365Connector(data_path=symphony_storage)
    connector.configuration = Office365Configuration(
        intake_key="foo",
        client_secret="bar",
        uuid="0000",
        intake_uuid="2222",
        community_uuid="3333",
        client_id="0",
        publisher_id="1",
        tenant_id="2",
        content_types={"json", "xml"},
    )

    connector.module.configuration = {}
    connector.log = Mock()
    connector.log_exception = Mock()
    connector.push_events_to_intakes = Mock()

    # Need the heavy artillery to override a property in a fixture
    monkeypatch.setattr("office365.management_api.connector.Office365Connector.client", client)
    yield connector


@pytest.fixture
def event():
    yield {"id": "42"}


@pytest.fixture
def other_event():
    yield {"id": "9000"}


@pytest.fixture
def tenant_id():
    yield str(uuid.uuid4())


@pytest.fixture
def mock_azure_authentication(requests_mock, tenant_id):
    requests_mock.get(
        f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration",
        status_code=200,
        json={
            "token_endpoint": f"https://login.microsoftonline.com/{tenant_id}/oauth2/token",
            "authorization_endpoint": f"https://login.microsoftonline.com/{tenant_id}/oauth2/authorize",
        },
    )
    requests_mock.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/token",
        status_code=200,
        json={"access_token": "access_token", "token_type": "Bearer", "expires_in": 0},
    )
    yield requests_mock


@pytest.fixture
def mock_azure_authentication_no_access_token(requests_mock, tenant_id):
    requests_mock.get(
        f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration",
        status_code=200,
        json={
            "token_endpoint": f"https://login.microsoftonline.com/{tenant_id}/oauth2/token",
            "authorization_endpoint": f"https://login.microsoftonline.com/{tenant_id}/oauth2/authorize",
        },
    )
    requests_mock.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/token",
        status_code=200,
        json={"token_type": "Bearer", "expires_in": 0},
    )
    yield requests_mock


@pytest.fixture
def mock_azure_authentication_wrong_token_type(requests_mock, tenant_id):
    requests_mock.get(
        f"https://login.microsoftonline.com/{tenant_id}/v2.0/.well-known/openid-configuration",
        status_code=200,
        json={
            "token_endpoint": f"https://login.microsoftonline.com/{tenant_id}/oauth2/token",
            "authorization_endpoint": f"https://login.microsoftonline.com/{tenant_id}/oauth2/authorize",
        },
    )
    requests_mock.post(
        f"https://login.microsoftonline.com/{tenant_id}/oauth2/token",
        status_code=200,
        json={"access_token": "access_token", "token_type": "foo", "expires_in": 0},
    )
    yield requests_mock
