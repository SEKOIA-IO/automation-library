import requests_mock

from microsoftdefender_modules import MicrosoftDefenderModule
from microsoftdefender_modules.action_isolate_machine import IsolateMachineAction
from microsoftdefender_modules.action_restrict_code_execution import RestrictCodeExecutionAction
from microsoftdefender_modules.action_scan_machine import ScanMachineAction


def configured_action(action):
    module = MicrosoftDefenderModule()
    a = action(module=module)

    a.module.configuration = {
        "app_id": "test_app_id",
        "app_secret": "test_app_secret",
        "tenant_id": "test_tenant_id",
    }

    return a


def test_isolate_machine_action():
    action = configured_action(IsolateMachineAction)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "POST",
            "https://api.securitycenter.microsoft.com/api/machines/1234/isolate",
            json={
                "@odata.context": "https://api.securitycenter.microsoft.com/api/$metadata#MachineActions/$entity",
                "id": "6b001073-5500-4205-8287-6f1184936f67",
                "type": "Isolate",
                "title": None,
                "requestor": "Integration MSGraph Security API",
                "requestorComment": "New new comment",
                "status": "Pending",
                "machineId": "1234",
                "computerDnsName": "windows11",
                "creationDateTimeUtc": "2024-10-21T11:25:48.3308187Z",
                "lastUpdateDateTimeUtc": "2024-10-21T11:25:48.330819Z",
                "cancellationRequestor": None,
                "cancellationComment": None,
                "cancellationDateTimeUtc": None,
                "errorHResult": 0,
                "scope": None,
                "externalId": None,
                "requestSource": "PublicApi",
                "relatedFileInfo": None,
                "commands": [],
                "troubleshootInfo": None,
            },
        )

        result = action.run(arguments={"machine_id": "1234", "comment": "Some comment"})

        assert result is not None


def test_scan_machine_action():
    action = configured_action(ScanMachineAction)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "POST",
            "https://api.securitycenter.microsoft.com/api/machines/1234/runAntiVirusScan",
            json={
                "@odata.context": "https://api.securitycenter.microsoft.com/api/$metadata#MachineActions/$entity",
                "id": "0696c900-b8ce-42ce-96f6-1b68268b7bea",
                "type": "RunAntiVirusScan",
                "title": None,
                "requestor": "Integration MSGraph Security API",
                "requestorComment": "New new comment",
                "status": "Pending",
                "machineId": "1234",
                "computerDnsName": "windows11",
                "creationDateTimeUtc": "2024-10-21T11:26:49.6894208Z",
                "lastUpdateDateTimeUtc": "2024-10-21T11:26:49.6894212Z",
                "cancellationRequestor": None,
                "cancellationComment": None,
                "cancellationDateTimeUtc": None,
                "errorHResult": 0,
                "scope": None,
                "externalId": None,
                "requestSource": "PublicApi",
                "relatedFileInfo": None,
                "commands": [],
                "troubleshootInfo": None,
            },
        )

        result = action.run(arguments={"machine_id": "1234", "comment": "Some comment"})

        assert result is not None


def test_restrict_code_execution_action():
    action = configured_action(RestrictCodeExecutionAction)

    with requests_mock.Mocker() as mock:
        mock.register_uri(
            "GET",
            "https://login.microsoftonline.com/test_tenant_id/oauth2/token",
            json={
                "access_token": "foo-token",
                "token_type": "bearer",
                "expires_in": 1799,
            },
        )

        mock.register_uri(
            "POST",
            "https://api.securitycenter.microsoft.com/api/machines/1234/restrictCodeExecution",
            json={
                "@odata.context": "https://api.securitycenter.microsoft.com/api/$metadata#MachineActions/$entity",
                "id": "ed74c544-91d4-414d-8805-5c26e028ef7e",
                "type": "RestrictCodeExecution",
                "title": None,
                "requestor": "Integration MSGraph Security API",
                "requestorComment": "New new comment",
                "status": "Pending",
                "machineId": "1234",
                "computerDnsName": "windows11",
                "creationDateTimeUtc": "2024-10-21T11:27:58.1447302Z",
                "lastUpdateDateTimeUtc": "2024-10-21T11:27:58.1447307Z",
                "cancellationRequestor": None,
                "cancellationComment": None,
                "cancellationDateTimeUtc": None,
                "errorHResult": 0,
                "scope": None,
                "externalId": None,
                "requestSource": "PublicApi",
                "relatedFileInfo": None,
                "commands": [],
                "troubleshootInfo": None,
            },
        )

        result = action.run(arguments={"machine_id": "1234", "comment": "Some comment"})

        assert result is not None
