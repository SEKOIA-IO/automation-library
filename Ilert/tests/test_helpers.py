from ilert.helpers import requests_retry_session


def test_requests_retry_session():
    session = requests_retry_session()
    assert session is not None
