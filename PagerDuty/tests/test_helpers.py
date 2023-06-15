# coding: utf-8

# internels
from pagerduty.helpers import requests_retry_session, urgency_to_pagerduty_severity


def test_requests_retry_session():
    session = requests_retry_session()
    assert session is not None


def test_urgency_to_pagerduty_severity():
    assert urgency_to_pagerduty_severity(-1) == "info"
    assert urgency_to_pagerduty_severity(5) == "info"
    assert urgency_to_pagerduty_severity(25) == "warning"
    assert urgency_to_pagerduty_severity(30) == "warning"
    assert urgency_to_pagerduty_severity(50) == "error"
    assert urgency_to_pagerduty_severity(67) == "error"
    assert urgency_to_pagerduty_severity(75) == "critical"
    assert urgency_to_pagerduty_severity(100) == "critical"
    assert urgency_to_pagerduty_severity(1000) == "critical"
