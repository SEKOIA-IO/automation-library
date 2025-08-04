from pytest import fixture

from beyondtrust_modules.helpers import parse_session, parse_session_end_time, parse_session_list


def test_parse_session_list(sessions_list_xml):
    session_ids = parse_session_list(sessions_list_xml)
    assert session_ids == ["e9e99aeb9ad54fb381634498502c5a1b", "219ca41dc71940a5a69687b49736d97b"]


def test_parse_session(session_xml):
    items = parse_session(session_xml)
    assert items == [
        {
            "timestamp": "1733239565",
            "event_type": "Session Start",
            "session_id": "e9e99aeb9ad54fb381634498502c5a1b",
            "jump_group": {"name": "Sekoia.io integration", "type": "shared"},
        },
        {
            "timestamp": "1733239565",
            "event_type": "Conference Owner Changed",
            "data": {"owner": "Pre-start Conference"},
            "destination": {"type": "system", "name": "Pre-start Conference"},
            "session_id": "e9e99aeb9ad54fb381634498502c5a1b",
            "jump_group": {"name": "Sekoia.io integration", "type": "shared"},
        },
    ]


def test_parse_end_time(session_xml):
    end_time = parse_session_end_time(session_xml)
    assert end_time == 1733240467
