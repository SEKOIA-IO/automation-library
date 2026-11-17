import pytest

from netskope_modules.types import NetskopeAlertType, NetskopeEventType


@pytest.mark.parametrize("enum_class", [NetskopeEventType, NetskopeAlertType])
def test_types_compare_with_their_raw_value(enum_class):
    # helpers.get_index_name compares the event type with a raw string
    for member in enum_class:
        assert member == member.value
        assert enum_class(member.value) is member


def test_event_types_values():
    assert {member.value for member in NetskopeEventType} == {
        "alert",
        "page",
        "application",
        "incident",
        "audit",
        "infrastructure",
        "network",
    }


def test_alert_types_values():
    assert {member.value for member in NetskopeAlertType} == {
        "dlp",
        "watchlist",
        "ctep",
        "compromisedcredential",
        "malsite",
        "malware",
        "policy",
        "remediation",
        "quarantine",
        "securityassessment",
        "uba",
    }
