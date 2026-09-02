from pytest import fixture

from beyondtrust_modules.helpers import parse_session, parse_session_end_time, parse_session_list

from .expectations import EXPECTED_SESSION_EVENTS


def test_parse_session_list(sessions_list_xml):
    session_ids = parse_session_list(sessions_list_xml)
    assert session_ids == ["e9e99aeb9ad54fb381634498502c5a1b", "219ca41dc71940a5a69687b49736d97b"]


def test_parse_session(session_xml):
    items = parse_session(session_xml)
    assert items == EXPECTED_SESSION_EVENTS


def test_parse_end_time(session_xml):
    end_time = parse_session_end_time(session_xml)
    assert end_time == 1733240467
