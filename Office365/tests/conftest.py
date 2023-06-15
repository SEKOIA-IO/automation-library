from datetime import datetime, timedelta, timezone
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
from sekoia_automation import constants


@pytest.fixture
def symphony_storage():
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
    return datetime.now(timezone.utc)


@pytest.fixture
def end_time(trigger_activation) -> datetime:
    return trigger_activation


@pytest.fixture
def start_time(trigger_activation) -> datetime:
    return trigger_activation - timedelta(minutes=1)
