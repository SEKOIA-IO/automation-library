from pytest import fixture

from beyondtrust_modules.helpers import parse_session
from beyondtrust_modules.helpers import parse_session_end_time
from beyondtrust_modules.helpers import parse_session_list
from beyondtrust_modules.helpers import parse_team
from beyondtrust_modules.helpers import parse_vault_activity

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


def test_parse_optional_branches():
    session_missing_fields_xml = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<session_list xmlns=\"http://www.beyondtrust.com/sra/namespaces/API/reporting\">
<session lsid=\"s1\">
    <jump_group type=\"shared\">JG</jump_group>
    <primary_customer>Alice</primary_customer>
    <customer_list>
        <customer>
            <private_ip>1.1.1.1</private_ip>
        </customer>
    </customer_list>
    <session_details>
        <event timestamp=\"1\" event_type=\"Evt\">
            <performed_by type=\"customer\">Alice</performed_by>
            <destination type=\"system\">Console</destination>
        </event>
    </session_details>
</session>
</session_list>"""

    events = parse_session(session_missing_fields_xml)
    assert len(events) == 1
    assert events[0]["performed_by"] == {"type": "customer", "name": "Alice"}
    assert events[0]["destination"] == {"type": "system", "name": "Console"}
    assert events[0]["primary_customer"] == {"name": "Alice"}
    assert "primary_rep" not in events[0]
    assert "file_transfer_count" not in events[0]

    session_empty_primary_name_xml = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<session_list xmlns=\"http://www.beyondtrust.com/sra/namespaces/API/reporting\">
<session lsid=\"s2\">
    <jump_group type=\"shared\">JG</jump_group>
    <primary_customer gsnumber=\"22\"></primary_customer>
    <customer_list>
        <customer gsnumber=\"22\">
            <public_ip>4.3.2.1:61606</public_ip>
        </customer>
    </customer_list>
    <session_details>
        <event timestamp=\"2\" event_type=\"Evt\" />
    </session_details>
</session>
</session_list>"""

    events_empty_name = parse_session(session_empty_primary_name_xml)
    assert events_empty_name[0]["primary_customer"] == {
        "gsnumber": "22",
        "public_ip": "4.3.2.1:61606",
    }

    vault_optional_xml = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<vault_account_activity_list xmlns=\"http://www.beyondtrust.com/sra/namespaces/API/reporting\">
   <vault_account_activity timestamp=\"1\" event_type=\"Account Created\" account=\"1\"/>
</vault_account_activity_list>"""
    vault_events = parse_vault_activity(vault_optional_xml)
    assert vault_events == [{"timestamp": "1", "account_id": "1", "event_type": "Account Created"}]

    team_optional_xml = b"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<team_activity_list xmlns=\"http://www.beyondtrust.com/sra/namespaces/API/reporting\">
    <team_activity name=\"T\" id=\"1\">
        <events>
            <event timestamp=\"1\" event_type=\"E\"/>
        </events>
    </team_activity>
</team_activity_list>"""
    team_events = parse_team(team_optional_xml)
    assert team_events == [
        {
            "timestamp": "1",
            "team": {"id": "1", "name": "T"},
            "performed_by": {},
            "event_type": "E",
            "data": {},
        }
    ]
