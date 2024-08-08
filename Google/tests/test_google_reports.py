import pytest
import os
from unittest.mock import Mock, patch

from freezegun import freeze_time

from google_module.google_reports import GoogleReports

import tempfile
import json
import codecs
import datetime


@pytest.fixture
def trigger(credentials):
    trigger = GoogleReports()
    trigger.module._configuration = dict(credentials)
    trigger.configuration = {
        "admin_mail": "admin_mail",
        "intake_key": "intake_key",
        "application_name": "drive",
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
                "id": {"time": "2023-08-07T12:04:37.532Z"},
                "etag": "etage1",
                "actor": {},
                "events": [],
            },
            {
                "kind": "admin#reports#activity",
                "id": {"time": "2023-08-07T12:03:37.532Z"},
                "etag": "etage2",
                "actor": {},
                "events": [],
            },
            {
                "kind": "admin#reports#activity",
                "id": {"time": "2023-08-07T12:02:37.532Z"},
                "etag": "etage3",
                "actor": {},
                "events": [],
            },
        ],
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
                "id": {"time": "2023-08-07T12:01:37.532Z"},
                "etag": "etage1",
                "actor": {},
                "events": [],
            },
            {
                "kind": "admin#reports#activity",
                "id": {"time": "2023-08-07T11:03:37.532Z"},
                "etag": "etage2",
                "actor": {},
                "events": [],
            },
            {
                "kind": "admin#reports#activity",
                "id": {"time": "2023-08-07T11:02:37.532Z"},
                "etag": "etage3",
                "actor": {},
                "events": [],
            },
        ],
    }


def test_get_reports_events(trigger, drive_response):
    with patch("google_module.google_reports.build", return_value=Mock()):
        with patch("google.oauth2.service_account.Credentials.from_service_account_file", return_value=Mock()):
            with patch("google_module.google_reports.GoogleReports.get_activities", return_value=drive_response):
                start_date = datetime.datetime(2023, 8, 7, 12, 1, 37)
                end_date = datetime.datetime(2023, 8, 7, 12, 4, 37)
                trigger.get_reports_events(start_date, end_date)
                results = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
                assert len(results[0]) == 3

                dict_result = [json.loads(result) for result in results[0]]
                assert dict_result[0]["id"]["time"] == "2023-08-07T12:04:37.532Z"
                assert dict_result[1]["id"]["time"] == "2023-08-07T12:03:37.532Z"
                assert dict_result[2]["id"]["time"] == "2023-08-07T12:02:37.532Z"


def test_drive_connector_NK(trigger, drive_response_NK, drive_response):
    with patch("google_module.google_reports.build", return_value=Mock()):
        with patch("google.oauth2.service_account.Credentials.from_service_account_file", return_value=Mock()):
            with patch("google_module.google_reports.GoogleReports.get_activities", return_value=drive_response_NK):
                with patch(
                    "google_module.google_reports.GoogleReports.get_reports_with_nk",
                    return_value=drive_response,
                ):
                    start_date = datetime.datetime(2023, 8, 7, 12, 1, 37)
                    end_date = datetime.datetime(2023, 8, 7, 12, 4, 37)
                    trigger.get_reports_events(start_date, end_date)
                    results = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
                    # 3 items because the first 3 items are pushed in the first call
                    assert len(results[0]) == 3

                    dict_result = [json.loads(result) for result in results[0]]
                    assert dict_result[2]["id"]["time"] == "2023-08-07T11:02:37.532Z"


def test_timestepper_corner_case(trigger):
    with freeze_time("2024-08-01 05:44:32", tick=True) as frozen_time, patch(
        "google_module.timestepper.time"
    ) as mock_time:
        mock_time.sleep.side_effect = lambda seconds: frozen_time.tick(datetime.timedelta(seconds=seconds))
        with trigger.context as cache:
            cache["most_recent_date_seen"] = "2024-08-01 04:50:32+00:00"

        # if difference between `most_recent_date_seen - now() <= timedelta`, then it will be ok
        # otherwise, we have to process a corner case
        trigger.configuration.timedelta = 60
        trigger.configuration.frequency = 10
        trigger.configuration.start_time = 1

        for i, (start, end) in enumerate(trigger.stepper.ranges()):
            assert start < end

            if i > 100:
                break


@pytest.mark.skipif(
    "{'GOOGLE_TYPE', 'GOOGLE_PROJECT_ID', 'GOOGLE_PRIVATE_KEY_ID', 'GOOGLE_PRIVATE_KEY', 'GOOGLE_CLIENT_EMAIL', 'GOOGLE_CLIENT_ID', 'GOOGLE_AUTH_URI', 'GOOGLE_TOKEN_URI', 'GOOGLE_AUTH_PROVIDER', 'GOOGLE_CLIENT_CERT', 'GOOGLE_UNIVERSE_DOMAIN', 'GOOGLE_ADMIN_MAIL'}.issubset(os.environ.keys()) == False"  # noqa
)
def test_get_google_reports_data_integration():
    trigger = GoogleReports()
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
        "universe_domain": os.environ["GOOGLE_UNIVERSE_DOMAIN"],
    }
    trigger.configuration = {
        "admin_mail": os.environ["GOOGLE_ADMIN_MAIL"],
        "intake_key": "intake_key",
        "application_name": "drive",
    }
    trigger.log = Mock()
    trigger.log_exception = Mock()
    trigger.push_events_to_intakes = Mock()

    temp_fd, temp_file_path = tempfile.mkstemp(suffix=".json", dir="./tests")
    with open(temp_file_path, "w") as json_file:
        json_string = json.dumps(trigger.module._configuration)
        decoded_json_string = codecs.decode(json_string, "unicode_escape")
        json_file.write(decoded_json_string)
        trigger.service_account_path = temp_file_path

    start_date = datetime.datetime(2023, 8, 7, 12, 1, 37)
    end_date = datetime.datetime(2023, 8, 7, 12, 4, 37)
    trigger.get_reports_events(start_date, end_date)
    os.close(temp_fd)
    os.remove(temp_file_path)
    results = [call.kwargs["events"] for call in trigger.push_events_to_intakes.call_args_list]
    assert len(results[0]) != 0
