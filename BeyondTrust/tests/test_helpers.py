from pytest import fixture

from beyondtrust_modules.helpers import _extract_ip, parse_session, parse_session_end_time, parse_session_list


def test_parse_session_list(sessions_list_xml):
    session_ids = parse_session_list(sessions_list_xml)
    assert session_ids == ["e9e99aeb9ad54fb381634498502c5a1b", "219ca41dc71940a5a69687b49736d97b"]


def test_parse_session(session_xml):
    items = parse_session(session_xml)
    customers = [{"username": "Sekoia.io integration", "public_ip": "4.231.237.19", "private_ip": "10.0.0.4"}]
    representatives = [{"username": "admin", "public_ip": "2a01:e34:ec57:b230:f188:56c5:7089:d987"}]

    assert items == [
        {
            "timestamp": "1733239565",
            "event_type": "Session Start",
            "session_id": "e9e99aeb9ad54fb381634498502c5a1b",
            "jump_group": {"name": "Sekoia.io integration", "type": "shared"},
            "customers": customers,
            "representatives": representatives,
        },
        {
            "timestamp": "1733239565",
            "event_type": "Conference Owner Changed",
            "data": {"owner": "Pre-start Conference"},
            "destination": {"type": "system", "name": "Pre-start Conference"},
            "session_id": "e9e99aeb9ad54fb381634498502c5a1b",
            "jump_group": {"name": "Sekoia.io integration", "type": "shared"},
            "customers": customers,
            "representatives": representatives,
        },
    ]


def test_parse_end_time(session_xml):
    end_time = parse_session_end_time(session_xml)
    assert end_time == 1733240467


class TestExtractIp:
    def test_ipv4_with_port(self):
        assert _extract_ip("4.231.237.19:61606") == "4.231.237.19"

    def test_ipv4_without_port(self):
        assert _extract_ip("10.0.0.4") == "10.0.0.4"

    def test_ipv6_with_port(self):
        assert _extract_ip("[2a01:e34:ec57:b230:f188:56c5:7089:d987]:56722") == "2a01:e34:ec57:b230:f188:56c5:7089:d987"

    def test_unknown(self):
        assert _extract_ip("Unknown") is None

    def test_none(self):
        assert _extract_ip(None) is None

    def test_empty(self):
        assert _extract_ip("") is None

    def test_unparsable(self):
        assert _extract_ip("not-an-ip") is None
