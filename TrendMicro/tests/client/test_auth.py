import pytest
from requests import Request

from trendmicro_modules.client.auth import TrendMicroVisionAuth


@pytest.mark.parametrize("method", ["GET", "POST"])
@pytest.mark.parametrize("api_key", ["secret-key", "another-secret"])
def test_trendmicro_vision_auth_adds_authorization_header(method, api_key):
    auth = TrendMicroVisionAuth(api_key=api_key)
    prepared = Request(method, "https://example.com").prepare()

    signed = auth(prepared)

    assert signed.headers["Authorization"] == f"Bearer {api_key}"
