import pytest
import requests_mock

from cybereason_modules.client.auth import CybereasonApiAuthentication
from cybereason_modules.exceptions import LoginFailureError
from tests.data import LOGIN_HTML


def test_authentication_failed():
    base_url = "https://fake.cybereason.net"
    username = "john.doe"
    password = "hypersecurepassword"
    session_id = "1234567890"
    auth = CybereasonApiAuthentication(base_url, username, password)

    with requests_mock.Mocker() as mock:
        jar = requests_mock.CookieJar()
        jar.set("JSESSIONID", session_id, domain="fake.cybereason.net")
        mock.post(f"{base_url}/login.html", status_code=200, cookies=jar, content=LOGIN_HTML)

        with pytest.raises(LoginFailureError):
            auth.get_credentials()
