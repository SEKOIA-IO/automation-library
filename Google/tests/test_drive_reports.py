import pytest
import os
from unittest.mock import Mock, patch
from google_module.google_drive_reports import DriveGoogleReports


@pytest.fixture
def trigger(credentials):
    trigger = DriveGoogleReports()
    trigger.module._configuration = dict(credentials)
    trigger.configuration = {
        "admin_mail": "admin_mail",
        "intake_key": "intake_key",
    }
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_events_to_intakes = Mock()
    return trigger


@pytest.fixture
def drive_response():
    return {
            "kind": "admin#reports#activities",
            "etag": "HT17nNOKg3qK25zh6p3L6mi",
            "nextPageToken": "",
            "items": [
                {
                    "kind": "admin#reports#activity",
                    "id": {},
                    "etag": "etage1",
                    "actor": {},
                    "events": []
                },
                {
                    "kind": "admin#reports#activity",
                    "id": {},
                    "etag": "etage2",
                    "actor": {},
                    "events": []
                },
                {
                    "kind": "admin#reports#activity",
                    "id": {},
                    "etag": "etage3",
                    "actor": {},
                    "events": []
                },
        ]
    }

@pytest.fixture
def drive_response_NK():
    return {
            "kind": "admin#reports#activities",
            "etag": "HT17nNOKg3qK25zh6p3L6mi",
            "nextPageToken": "nextpagetoken_99",
            "items": [
                {
                    "kind": "admin#reports#activity",
                    "id": {},
                    "etag": "etage1",
                    "actor": {},
                    "events": []
                },
                {
                    "kind": "admin#reports#activity",
                    "id": {},
                    "etag": "etage2",
                    "actor": {},
                    "events": []
                },
                {
                    "kind": "admin#reports#activity",
                    "id": {},
                    "etag": "etage3",
                    "actor": {},
                    "events": []
                },
        ]
    }


def test_get_google_reports_data(trigger, drive_response):

    mock_service = Mock()
    mock_service.activities.return_value.list.return_value.execute.return_value = drive_response

    with patch('google_module.google_drive_reports.build', return_value=mock_service):
        with patch('google.oauth2.service_account.Credentials.from_service_account_file', return_value=Mock()):

            trigger.get_repots_evts()
            resultats = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
            assert len(resultats[0]) != 0
            assert trigger.events_sum == 3


def test_drive_connector_NK(trigger, drive_response_NK, drive_response):
    with patch('google_module.google_drive_reports.build', return_value=Mock()):
        with patch('google.oauth2.service_account.Credentials.from_service_account_file', return_value=Mock()): 
            with patch('google_module.google_drive_reports.DriveGoogleReports.get_activities', return_value=drive_response_NK):
               with patch('google_module.google_drive_reports.DriveGoogleReports.get_next_activities', return_value=drive_response): 

                    trigger.get_repots_evts()
                    resultats = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
                    assert len(resultats[0]) != 0
                    assert trigger.events_sum == 6


@pytest.mark.skipif(
    "{'GOOGLE_TYPE', 'GOOGLE_PROJECT_ID', 'GOOGLE_PRIVATE_KEY_ID', 'GOOGLE_PRIVATE_KEY', 'GOOGLE_CLIENT_EMAIL', 'GOOGLE_CLIENT_ID', 'GOOGLE_AUTH_URI', 'GOOGLE_TOKEN_URI', 'GOOGLE_AUTH_PROVIDER', 'GOOGLE_CLIENT_CERT', 'GOOGLE_UNIVERSE_DOMAIN', 'GOOGLE_ADMIN_MAIL'}.issubset(os.environ.keys()) == False"  # noqa
)
def test_get_google_reports_data_integration():
    trigger = DriveGoogleReports()
    trigger.module._configuration = {
  "type": os.environ["GOOGLE_TYPE"],
  "project_id": os.environ["GOOGLE_PROJECT_ID"],
  "private_key_id": os.environ["GOOGLE_PRIVATE_KEY_ID"],
  "private_key": os.environ["GOOGLE_PRIVATE_KEY"],
  "client_email": os.environ["GOOGLE_CLIENT_EMAIL"],
  "client_id": os.environ["GOOGLE_CLIENT_ID"],
  "auth_uri": os.environ["GOOGLE_AUTH_URI"],
  "token_uri": os.environ["GOOGLE_TOKEN_URI"],
  "auth_provider_x509_cert_url": os.environ["GOOGLE_AUTH_PROVIDER"],
  "client_x509_cert_url": os.environ["GOOGLE_CLIENT_CERT"],
  "universe_domain": os.environ["GOOGLE_UNIVERSE_DOMAIN"]
}
    trigger.configuration = {
        "admin_mail": os.environ["GOOGLE_ADMIN_MAIL"],
        "intake_key": "intake_key",
    }
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_events_to_intakes = Mock()
    trigger.get_repots_evts()
    resultats = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(resultats[0]) != 0