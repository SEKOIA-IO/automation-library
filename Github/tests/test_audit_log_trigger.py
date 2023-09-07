from unittest.mock import MagicMock, patch

import pytest
import requests_mock

from github_modules import GithubModule
from github_modules.audit_log_trigger import AuditLogConnector


@pytest.fixture
def trigger(symphony_storage):
    module = GithubModule()
    trigger = AuditLogConnector(module=module, data_path=symphony_storage)
    # mock the log function of trigger that requires network access to the api for reporting
    trigger.log = MagicMock()
    trigger.log_exception = MagicMock()
    trigger._push_data_to_intake = MagicMock()
    trigger.module.configuration = {
        "apikey": "ghp_AAA",
        "org_name": "Test-org",
    }
    trigger.configuration = {
        "intake_key": "intake_key",
    }
    yield trigger


@pytest.fixture
def message1():
    # flake8: noqa
    return [
        {
            "@timestamp": 1685465626150,
            "_document_id": "aCjok7V1YYqP1c9IE6qbkg",
            "action": "org.block_user",
            "actor": "Admin",
            "actor_id": 6123123,
            "actor_location": {"country_code": "FR"},
            "blocked_user": "aaa",
            "created_at": 1685465626150,
            "operation_type": "create",
            "org": "Test-org",
            "org_id": 123123995,
            "user_agent": "Mozilla/5.0 (Linux; Android 12; SM-S906N Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36",
        },
        {
            "@timestamp": 1685465627991,
            "_document_id": "gMzuZXn3m1ewbOR6RkNnLw",
            "action": "org.unblock_user",
            "actor": "Admin",
            "actor_id": 6123123,
            "actor_location": {"country_code": "FR"},
            "blocked_user": "aaa",
            "created_at": 1685465627991,
            "operation_type": "remove",
            "org": "Test-org",
            "org_id": 123123995,
            "user_agent": "Mozilla/5.0 (Linux; Android 12; SM-S906N Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36",
        },
        {
            "@timestamp": 1685465630880,
            "_document_id": "UKmJTzlW7D2OvZ5F3GrpnA",
            "action": "org.block_user",
            "actor": "Admin",
            "actor_id": 6123123,
            "actor_location": {"country_code": "FR"},
            "blocked_user": "aaa",
            "created_at": 1685465630880,
            "operation_type": "create",
            "org": "Test-org",
            "org_id": 123123995,
            "user_agent": "Mozilla/5.0 (Linux; Android 12; SM-S906N Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36",
        },
        {
            "@timestamp": 1685465633434,
            "_document_id": "Ih4X_g0X7Ots5Mr6O-eozA",
            "action": "org.unblock_user",
            "actor": "Admin",
            "actor_id": 6123123,
            "actor_location": {"country_code": "FR"},
            "blocked_user": "aaa",
            "created_at": 1685465633434,
            "operation_type": "remove",
            "org": "Test-org",
            "org_id": 123123995,
            "user_agent": "Mozilla/5.0 (Linux; Android 12; SM-S906N Build/QP1A.190711.020; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/80.0.3987.119 Mobile Safari/537.36",
        },
    ]
    # flake8: qa


def test_next_batch(trigger, message1):
    with patch("github_modules.audit_log_trigger.time") as mock_time, requests_mock.Mocker() as mock_request:
        last_ts = 1685465627.991
        batch_start = 1685465690.881
        batch_end = 1685465633.434
        mock_request.get(
            "https://api.github.com/orgs/"
            + trigger.module.configuration.org_name
            + "/audit-log?phrase=created%3A%3E"
            + str(round(last_ts * 1000) - 60000)
            + "&order=asc",
            json=message1,
        )

        mock_time.time.side_effect = [batch_start, last_ts, last_ts, batch_end]
        trigger.next_batch()

        # Check that the result is well filtered
        # assert events_sent == expected_events
        calls = [call.kwargs["events"] for call in trigger._push_data_to_intake.call_args_list]
        assert len(calls[0]) == 3
        assert trigger._push_data_to_intake.call_count == 1
