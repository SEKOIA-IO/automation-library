import pytest
import os
import json
from glimps.models import GLIMPSConfiguration, ProfileStatus
from glimps.get_status_action import GetStatus
from unittest.mock import patch
import requests


@pytest.mark.skipif("{'GLIMPS_API_KEY', 'GLIMPS_API_URL'}.issubset(os.environ.keys()) == False")
def test_integration_get_status():
    action = GetStatus()
    action.module.configuration = GLIMPSConfiguration(
        api_key=os.environ["GLIMPS_API_KEY"], base_url="https://gmalware.ggp.glimps.re"
    )

    response: ProfileStatus = action.run({})
    assert response is not None
    assert response.get("daily_quota", 0) > 0


def test_get_status_error(module):
    action = GetStatus(module=module)

    with patch("gdetect.api.Client._request") as mock:
        r = requests.Response()
        http_resp = {"status": False, "error": "unauthorized"}
        r._content = json.dumps(http_resp).encode("utf-8")
        r.status_code = 401
        mock.return_value = r

        response = action.run({})
        assert response.get("daily_quota") == 0
        assert response.get("available_daily_quota") == 0
        assert response.get("estimated_analysis_duration") == 0


def test_get_status_ok(module):
    action = GetStatus(module=module)

    with patch("gdetect.api.Client._request") as mock:
        r = requests.Response()
        http_resp = {
            "daily_quota": 10,
            "available_daily_quota": 15,
            "estimated_analysis_duration": 100,
        }
        r._content = json.dumps(http_resp).encode("utf-8")
        r.status_code = 200
        mock.return_value = r

        response = action.run({})
        assert response.get("daily_quota") == 10
        assert response.get("available_daily_quota") == 15
        assert response.get("estimated_analysis_duration") == 100
        assert response.get("cache") is False
