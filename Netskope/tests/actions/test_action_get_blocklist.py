from unittest.mock import MagicMock

import requests_mock

from netskope_modules.actions.action_get_blocklist import GetBlocklistAction


def test_get_blocklist_success(symphony_storage, trigger):
    trigger.module.configuration.base_url = "https://my.fake.netskope.com"
    action = GetBlocklistAction(module=trigger.module, data_path=symphony_storage)
    action.log = MagicMock()
    action.log_exception = MagicMock()

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            "https://my.fake.netskope.com/api/v2/policy/urllist/123",
            status_code=200,
            json={
                "id": 123,
                "name": "Test Blocklist",
                "data": {"type": "exact", "urls": ["www.a.com", "www.b.com"]},
            },
        )

        result = action.run({"api_token": "fake_api_token", "blocklist_id": "123"})

        assert result["action_name"] == "get_blocklist"
        assert "curl -X 'GET'" in result["action_request"]
        assert "'https://my.fake.netskope.com/api/v2/policy/urllist/123'" in result["action_request"]
        assert "-H 'accept: application/json'" in result["action_request"]
        assert result["action_response"]["id"] == 123
        assert "Successfully fetched blocklist Test Blocklist (id = 123)" in result["action_status"]
