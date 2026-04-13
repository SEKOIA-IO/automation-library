# coding: utf-8
"""
Various helping functions
"""

# third parties
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def requests_retry_session(
    retries=3,
    backoff_factor=10,
    status_forcelist=(429, 500, 502, 504),
    session=None,
):
    """
    Retry implementation on HTTP requests to handle transient failures
    and 429 rate limit responses from the ilert Events API.
    """
    session = session or requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session
