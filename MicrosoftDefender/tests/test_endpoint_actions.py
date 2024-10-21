import requests_mock
from microsoftdefender_modules.action_restrict_code_execution import RestrictCodeExecutionAction
from microsoftdefender_modules.action_scan_machine import ScanMachineAction
from microsoftdefender_modules.action_stop_and_quarantine_file import StopAndQuarantineFileAction
from microsoftdefender_modules.action_unisolate_machine import UnIsolateMachineAction
from microsoftdefender_modules.action_unrestrict_code_execution import UnRestrictCodeExecutionAction
from microsoftdefender_modules.action_update_alert import UpdateAlertAction
from microsoftdefender_modules import MicrosoftDefenderModule, MicrosoftDefenderModuleConfiguration
from microsoftdefender_modules.action_get_machine_action import GetMachineAction
from microsoftdefender_modules.action_isolate_machine import IsolateMachineAction


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
            json={}
        )

        result = action.run(arguments={
            "machine_id": "1234",
            "comment": "Some comment"
        })

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
            json={}
        )

        result = action.run(arguments={
            "machine_id": "1234",
            "comment": "Some comment"
        })

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
            json={}
        )

        result = action.run(arguments={
            "machine_id": "1234",
            "comment": "Some comment"
        })

        assert result is not None
