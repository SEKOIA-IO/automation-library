import os
from unittest.mock import Mock

import pytest

from aether_endpoint_security_api import RetrievesListOfDevices


@pytest.mark.skipif(
    "{'WG_API_KEY', 'WG_ACCOUNT_ID', 'WG_ACCESS_ID', \
            'WG_ACCESS_SECRET'}.issubset(os.environ.keys()) == False"
)
def test_authorization():
    action = RetrievesListOfDevices()
    action.module.configuration = {
        "account_id": os.environ["WG_ACCOUNT_ID"],
        "api_key": os.environ["WG_API_KEY"],
        "access_id": os.environ["WG_ACCESS_ID"],
        "access_secret": os.environ["WG_ACCESS_SECRET"],
        "base_url": os.environ.get("WG_BASE_URI", "https://api.usa.cloud.watchguard.com"),
    }
    action._arguments = action.module.configuration

    # headers = action.get_headers()
    # url = action.get_url(action._arguments)
    # body = action.get_body(action._arguments)
    # import requests
    # response = requests.get(url, headers=headers)

    action.send_results = Mock()
    response = action.run(action.arguments)

    assert response is not None
    assert len(response.get("data", [])) > 0
