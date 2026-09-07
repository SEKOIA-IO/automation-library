from unittest.mock import MagicMock

import requests_mock

from netskope_modules.actions.action_deploy_url_policy import DeployUrlPolicyAction
from netskope_modules.actions.action_quarantine_file import QuarantineFileAction
from netskope_modules.actions.action_restrict_file_shares import (
    RestrictFileSharesAction,
)
from netskope_modules.actions.action_restrict_user_to_group import (
    RestrictUserToGroupAction,
)
from netskope_modules.actions.action_revoke_user_sessions import (
    RevokeUserSessionsAction,
)
from netskope_modules.actions.action_update_dlp_incident_status import (
    UpdateDlpIncidentStatusAction,
)


def build_action(action_class, trigger, symphony_storage):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = action_class(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()
    return action


def test_deploy_url_policy_success(symphony_storage, trigger):
    action = build_action(DeployUrlPolicyAction, trigger, symphony_storage)

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/policy/urllist/deploy",
            status_code=200,
            json={},
        )

        result = action.run({"api_token": "fake_api_token"})

        assert result is None
        action.log.assert_any_call(level="info", message="Successfully deployed pending URL policy changes")


def test_restrict_user_to_group_success(symphony_storage, trigger):
    action = build_action(RestrictUserToGroupAction, trigger, symphony_storage)

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/scim/Users",
            status_code=200,
            json={"Resources": [{"id": "user-123", "userName": "alice@example.com"}]},
        )
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/scim/Users/user-123",
            status_code=200,
            json={"id": "user-123"},
        )

        result = action.run(
            {
                "api_token": "fake_api_token",
                "user_name": "alice@example.com",
                "group_ids": ["group-1", "group-2"],
            }
        )

        assert result is None
        assert mock_requests.request_history[1].json() == {"groups": [{"value": "group-1"}, {"value": "group-2"}]}
        action.log.assert_any_call(
            level="info",
            message='Successfully restricted Netskope user "alice@example.com" (id = user-123) to 2 group(s)',
        )


def test_revoke_user_sessions_success(symphony_storage, trigger):
    action = build_action(RevokeUserSessionsAction, trigger, symphony_storage)

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/events/token/revoke",
            status_code=200,
            json={},
        )

        result = action.run({"api_token": "fake_api_token", "user_name": "alice@example.com"})

        assert result is None
        assert mock_requests.request_history[0].json() == {"userName": "alice@example.com"}
        action.log.assert_any_call(
            level="info",
            message='Successfully revoked active Netskope sessions for "alice@example.com"',
        )


def test_quarantine_file_success(symphony_storage, trigger):
    action = build_action(QuarantineFileAction, trigger, symphony_storage)

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/infrastructure/remediation/quarantine",
            status_code=200,
            json={},
        )

        result = action.run({"api_token": "fake_api_token", "file_id": "file-123"})

        assert result is None
        assert mock_requests.request_history[0].json() == {"file_id": "file-123"}
        action.log.assert_any_call(level="info", message='Successfully quarantined file "file-123"')


def test_restrict_file_shares_unshare_success(symphony_storage, trigger):
    action = build_action(RestrictFileSharesAction, trigger, symphony_storage)

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/infrastructure/remediation/unshare",
            status_code=200,
            json={},
        )

        result = action.run({"api_token": "fake_api_token", "file_id": "file-123"})

        assert result is None
        assert mock_requests.request_history[0].json() == {"file_id": "file-123"}
        action.log.assert_any_call(
            level="info",
            message='Successfully applied "unshare" remediation to file "file-123"',
        )


def test_restrict_file_shares_restrict_access_success(symphony_storage, trigger):
    action = build_action(RestrictFileSharesAction, trigger, symphony_storage)

    with requests_mock.Mocker() as mock_requests:
        mock_requests.post(
            "https://my.fake.netskope.com/api/v2/infrastructure/remediation/restrict-access",
            status_code=200,
            json={},
        )

        result = action.run(
            {
                "api_token": "fake_api_token",
                "file_id": "file-123",
                "operation": "restrict-access",
            }
        )

        assert result is None
        assert mock_requests.request_history[0].json() == {"file_id": "file-123"}
        action.log.assert_any_call(
            level="info",
            message='Successfully applied "restrict-access" remediation to file "file-123"',
        )


def test_update_dlp_incident_status_success(symphony_storage, trigger):
    action = build_action(UpdateDlpIncidentStatusAction, trigger, symphony_storage)

    with requests_mock.Mocker() as mock_requests:
        mock_requests.patch(
            "https://my.fake.netskope.com/api/v2/dlp/incident/inc-123",
            status_code=200,
            json={},
        )

        result = action.run(
            {
                "api_token": "fake_api_token",
                "incident_id": "inc-123",
                "status": "closed",
                "notes": "Remediated by playbook",
            }
        )

        assert result is None
        assert mock_requests.request_history[0].json() == {
            "status": "closed",
            "notes": "Remediated by playbook",
        }
        action.log.assert_any_call(
            level="info",
            message='Successfully updated DLP incident "inc-123" to "closed"',
        )
