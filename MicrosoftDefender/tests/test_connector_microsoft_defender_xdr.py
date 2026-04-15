import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from sekoia_automation.storage import PersistentJSON

from microsoftdefender_modules import MicrosoftDefenderModule
from microsoftdefender_modules.connector_microsoft_defender_xdr import MicrosoftDefenderGraphAPIAlerts

LOGGER = logging.getLogger(__name__)


@pytest.fixture
def trigger(data_storage):
    module = MicrosoftDefenderModule()
    module.configuration = {
        "tenant_id": "aa",
        "app_id": "aa",
        "app_secret": "aa",
    }
    trigger = MicrosoftDefenderGraphAPIAlerts(module=module, data_path=data_storage)
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_events_to_intakes = Mock()
    trigger.configuration = {
        "intake_key": "aa",
        "frequency": 60,
        "start_time": 0,
        "timedelta": 0,
    }
    yield trigger


@pytest.fixture
def trigger_activation() -> datetime:
    return datetime.now(timezone.utc)


@pytest.fixture
def end_time(trigger_activation) -> datetime:
    return trigger_activation


@pytest.fixture
def start_time(trigger_activation) -> datetime:
    return trigger_activation - timedelta(minutes=1)


@pytest.fixture
def message():
    # Source: https://learn.microsoft.com/en-us/graph/api/security-list-alerts_v2?view=graph-rest-1.0&tabs=http#response-1
    return {
        "value": [
            {
                "@odata.type": "#microsoft.graph.security.alert",
                "id": "da637551227677560813_-961444813",
                "providerAlertId": "da637551227677560813_-961444813",
                "incidentId": "28282",
                "status": "new",
                "severity": "low",
                "classification": "unknown",
                "determination": "unknown",
                "serviceSource": "microsoftDefenderForEndpoint",
                "detectionSource": "antivirus",
                "detectorId": "e0da400f-affd-43ef-b1d5-afc2eb6f2756",
                "tenantId": "b3c1b5fc-828c-45fa-a1e1-10d74f6d6e9c",
                "title": "Suspicious execution of hidden file",
                "description": "A hidden file has been launched. This activity could indicate a compromised host. Attackers often hide files associated with malicious tools to evade file system inspection and defenses.",
                "recommendedActions": "Collect artifacts and determine scope\n�\tReview the machine timeline for suspicious activities that may have occurred before and after the time of the alert, and record additional related artifacts (files, IPs/URLs) \n�\tLook for the presence of relevant artifacts on other systems. Identify commonalities and differences between potentially compromised systems.\n�\tSubmit relevant files for deep analysis and review resulting detailed behavioral information.\n�\tSubmit undetected files to the MMPC malware portal\n\nInitiate containment & mitigation \n�\tContact the user to verify intent and initiate local remediation actions as needed.\n�\tUpdate AV signatures and run a full scan. The scan might reveal and remove previously-undetected malware components.\n�\tEnsure that the machine has the latest security updates. In particular, ensure that you have installed the latest software, web browser, and Operating System versions.\n�\tIf credential theft is suspected, reset all relevant users passwords.\n�\tBlock communication with relevant URLs or IPs at the organization�s perimeter.",
                "category": "DefenseEvasion",
                "assignedTo": None,
                "alertWebUrl": "https://security.microsoft.com/alerts/da637551227677560813_-961444813?tid=b3c1b5fc-828c-45fa-a1e1-10d74f6d6e9c",
                "incidentWebUrl": "https://security.microsoft.com/incidents/28282?tid=b3c1b5fc-828c-45fa-a1e1-10d74f6d6e9c",
                "actorDisplayName": None,
                "threatDisplayName": None,
                "threatFamilyName": None,
                "mitreTechniques": ["T1564.001"],
                "createdDateTime": "2021-04-27T12:19:27.7211305Z",
                "lastUpdateDateTime": "2021-05-02T14:19:01.3266667Z",
                "resolvedDateTime": None,
                "firstActivityDateTime": "2021-04-26T07:45:50.116Z",
                "lastActivityDateTime": "2021-05-02T07:56:58.222Z",
                "comments": [],
                "evidence": [
                    {
                        "@odata.type": "#microsoft.graph.security.deviceEvidence",
                        "createdDateTime": "2021-04-27T12:19:27.7211305Z",
                        "verdict": "unknown",
                        "remediationStatus": "none",
                        "remediationStatusDetails": None,
                        "firstSeenDateTime": "2020-09-12T07:28:32.4321753Z",
                        "mdeDeviceId": "73e7e2de709dff64ef64b1d0c30e67fab63279db",
                        "azureAdDeviceId": None,
                        "deviceDnsName": "yonif-lap3.middleeast.corp.microsoft.com",
                        "hostName": "yonif-lap3",
                        "ntDomain": None,
                        "dnsDomain": "middleeast.corp.microsoft.com",
                        "osPlatform": "Windows10",
                        "osBuild": 22424,
                        "version": "Other",
                        "healthStatus": "active",
                        "riskScore": "medium",
                        "rbacGroupId": 75,
                        "rbacGroupName": "UnassignedGroup",
                        "onboardingStatus": "onboarded",
                        "defenderAvStatus": "unknown",
                        "ipInterfaces": ["1.1.1.1"],
                        "loggedOnUsers": [],
                        "roles": ["compromised"],
                        "detailedRoles": ["Main device"],
                        "tags": ["Test Machine"],
                        "vmMetadata": {
                            "vmId": "ca1b0d41-5a3b-4d95-b48b-f220aed11d78",
                            "cloudProvider": "azure",
                            "resourceId": "/subscriptions/8700d3a3-3bb7-4fbe-a090-488a1ad04161/resourceGroups/WdatpApi-EUS-STG/providers/Microsoft.Compute/virtualMachines/NirLaviTests",
                            "subscriptionId": "8700d3a3-3bb7-4fbe-a090-488a1ad04161",
                        },
                    },
                    {
                        "@odata.type": "#microsoft.graph.security.fileEvidence",
                        "createdDateTime": "2021-04-27T12:19:27.7211305Z",
                        "verdict": "unknown",
                        "remediationStatus": "none",
                        "remediationStatusDetails": None,
                        "detectionStatus": "detected",
                        "mdeDeviceId": "73e7e2de709dff64ef64b1d0c30e67fab63279db",
                        "roles": [],
                        "detailedRoles": ["Referred in command line"],
                        "tags": [],
                        "fileDetails": {
                            "sha1": "5f1e8acedc065031aad553b710838eb366cfee9a",
                            "sha256": "8963a19fb992ad9a76576c5638fd68292cffb9aaac29eb8285f9abf6196a7dec",
                            "fileName": "MsSense.exe",
                            "filePath": "C:\\Program Files\\temp",
                            "fileSize": 6136392,
                            "filePublisher": "Microsoft Corporation",
                            "signer": None,
                            "issuer": None,
                        },
                    },
                    {
                        "@odata.type": "#microsoft.graph.security.processEvidence",
                        "createdDateTime": "2021-04-27T12:19:27.7211305Z",
                        "verdict": "unknown",
                        "remediationStatus": "none",
                        "remediationStatusDetails": None,
                        "processId": 4780,
                        "parentProcessId": 668,
                        "processCommandLine": '"MsSense.exe"',
                        "processCreationDateTime": "2021-08-12T12:43:19.0772577Z",
                        "parentProcessCreationDateTime": "2021-08-12T07:39:09.0909239Z",
                        "detectionStatus": "detected",
                        "mdeDeviceId": "73e7e2de709dff64ef64b1d0c30e67fab63279db",
                        "roles": [],
                        "detailedRoles": [],
                        "tags": [],
                        "imageFile": {
                            "sha1": "5f1e8acedc065031aad553b710838eb366cfee9a",
                            "sha256": "8963a19fb992ad9a76576c5638fd68292cffb9aaac29eb8285f9abf6196a7dec",
                            "fileName": "MsSense.exe",
                            "filePath": "C:\\Program Files\\temp",
                            "fileSize": 6136392,
                            "filePublisher": "Microsoft Corporation",
                            "signer": None,
                            "issuer": None,
                        },
                        "parentProcessImageFile": {
                            "sha1": None,
                            "sha256": None,
                            "fileName": "services.exe",
                            "filePath": "C:\\Windows\\System32",
                            "fileSize": 731744,
                            "filePublisher": "Microsoft Corporation",
                            "signer": None,
                            "issuer": None,
                        },
                        "userAccount": {
                            "accountName": "SYSTEM",
                            "domainName": "NT AUTHORITY",
                            "userSid": "S-1-5-18",
                            "azureAdUserId": None,
                            "userPrincipalName": None,
                            "displayName": "System",
                        },
                    },
                    {
                        "@odata.type": "#microsoft.graph.security.registryKeyEvidence",
                        "createdDateTime": "2021-04-27T12:19:27.7211305Z",
                        "verdict": "unknown",
                        "remediationStatus": "none",
                        "remediationStatusDetails": None,
                        "registryKey": "SYSTEM\\CONTROLSET001\\CONTROL\\WMI\\AUTOLOGGER\\SENSEAUDITLOGGER",
                        "registryHive": "HKEY_LOCAL_MACHINE",
                        "roles": [],
                        "detailedRoles": [],
                        "tags": [],
                    },
                ],
                "systemTags": ["Defender Experts"],
            }
        ]
    }


def test_fetch_events(trigger, requests_mock, message, start_time, end_time):
    with patch("microsoftdefender_modules.client.auth.msal.ConfidentialClientApplication") as mock_msal:
        mock_msal.acquire_token_silent = MagicMock()
        mock_msal.acquire_token_silent.return_value = {"access_token": "TOKEN"}

        trigger._get_access_token = Mock()
        requests_mock.get(
            "https://graph.microsoft.com/v1.0/security/alerts_v2",
            json=message,
        )
        gen = trigger.fetch_events(start_time, end_time)
        for events in gen:
            assert type(events) is list


def test_fetch_events_wrong_json(trigger, requests_mock, start_time, end_time):
    with patch("microsoftdefender_modules.client.auth.msal.ConfidentialClientApplication") as mock_msal:
        mock_msal.acquire_token_silent = MagicMock()
        mock_msal.acquire_token_silent.return_value = {"access_token": "TOKEN"}

        trigger._get_access_token = Mock()
        requests_mock.get(
            "https://graph.microsoft.com/v1.0/security/alerts_v2",
            text="{}",
        )
        events = trigger.fetch_events(start_time, end_time)
        assert list(events) == []


def test_stepper_with_cursor(trigger, data_storage):
    date = datetime.now(timezone.utc)
    most_recent_date_requested = date - timedelta(days=6)
    context = PersistentJSON("context.json", data_storage)

    with context as cache:
        cache["most_recent_date_requested"] = most_recent_date_requested.isoformat()

    with patch("microsoftdefender_modules.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime.now(timezone.utc)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start == most_recent_date_requested


def test_stepper_with_cursor_older_than_30_days(trigger, data_storage):
    context = PersistentJSON("context.json", data_storage)

    fixed_now = datetime(2026, 3, 16, 1, 12, 00, tzinfo=timezone.utc)
    most_recent_date_requested = fixed_now - timedelta(days=40)
    expected_date = fixed_now - timedelta(days=30)

    with context as cache:
        cache["most_recent_date_requested"] = most_recent_date_requested.isoformat()

    with patch("microsoftdefender_modules.connector_microsoft_defender_xdr.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_now
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start.replace(microsecond=0) == expected_date.replace(microsecond=0)


def test_stepper_without_cursor(trigger, data_storage):
    context = PersistentJSON("context.json", data_storage)

    # ensure that the cursor is None
    with context as cache:
        cache["most_recent_date_requested"] = None

    with patch("microsoftdefender_modules.timestepper.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 3, 22, 11, 56, 28, tzinfo=timezone.utc)
        mock_datetime.side_effect = lambda *args, **kw: datetime(*args, **kw)

        assert trigger.stepper.start == datetime(2023, 3, 22, 11, 55, 28, tzinfo=timezone.utc)


def test_process_events(trigger, message):
    batch_of_events = message["value"]
    processed_events = list(trigger.process_events(batch_of_events))
    assert len(processed_events) == 5  # 1 alert + 4 evidences

    event_alert = processed_events[0]
    assert "evidence" not in event_alert

    alert_id = event_alert["id"]
    for evidence in processed_events[1:]:
        assert "alertId" in evidence
        assert evidence["alertId"] == alert_id
