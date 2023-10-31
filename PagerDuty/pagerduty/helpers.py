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
    Retry implementation on HTTP requests
    to follow the PagerDuty recommendations (https://developer.pagerduty.com/docs/events-api-v2/trigger-events/):

    > If the service has received too many events, a 429 Too Many Requests response will be returned.
    > If it is vital that all events your monitoring tool sends be received,
    > be sure to retry on a 429 response code (preferably with a backoff period).

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


def urgency_to_pagerduty_severity(urgency: int) -> str:
    """
    Returns the PagerDuty severity label that best matches
    with the specified Sekoia.io urgency score
    """

    if urgency < 25:
        return "info"
    elif urgency < 50:
        return "warning"
    elif urgency < 75:
        return "error"
    else:
        return "critical"
