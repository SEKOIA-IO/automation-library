from typing import Any

from lxml import etree

# Fields describing a participant of a session, reported under customer_list/rep_list
PARTICIPANT_FIELDS = ("private_ip", "public_ip", "hostname", "os")

# Session wide counters, useful to monitor exfiltration
SESSION_COUNTERS = ("file_transfer_count", "file_move_count", "file_delete_count")


def _parse_participants(root: Any, namespace: dict[str, str]) -> dict[str, dict[str, str]]:
    """Index the participants of a session (customers and representatives) by their gsnumber.

    The gsnumber is the correlation key between a participant of the session and the
    performed_by of an individual event of this session.
    """
    participants: dict[str, dict[str, str]] = {}

    elements = root.xpath(
        "/ns:session_list/ns:session/ns:customer_list/ns:customer"
        "|/ns:session_list/ns:session/ns:rep_list/ns:representative",
        namespaces=namespace,
    )
    for element in elements:
        gsnumber = element.attrib.get("gsnumber")
        if not gsnumber:
            continue

        details = {}
        for field in PARTICIPANT_FIELDS:
            value = element.findtext(f"ns:{field}", namespaces=namespace)

            # BeyondTrust reports the values it failed to collect as the literal string "Unknown"
            if value and value != "Unknown":
                details[field] = value

        participants[gsnumber] = details

    return participants


def _parse_primary_participant(
    root: Any, tag: str, participants: dict[str, dict[str, str]], namespace: dict[str, str]
) -> dict[str, str]:
    """Describe the primary customer or the primary representative of a session."""
    elements = root.xpath(f"/ns:session_list/ns:session/ns:{tag}", namespaces=namespace)
    if not elements:
        return {}

    element = elements[0]
    result: dict[str, str] = {}

    if element.text:
        result["name"] = element.text

    gsnumber = element.attrib.get("gsnumber")
    if gsnumber:
        result["gsnumber"] = gsnumber
        result.update(participants.get(gsnumber, {}))

    return result


def _describe_element(element: Any, participants: dict[str, dict[str, str]] | None = None) -> dict[str, str]:
    """Describe the performer or the destination of an event.

    When participants are supplied, the details of the matching participant are merged in.
    """
    result = {
        "type": element.attrib["type"],
        "name": element.text,
    }

    gsnumber = element.attrib.get("gsnumber")
    if gsnumber:
        result["gsnumber"] = gsnumber
        result.update((participants or {}).get(gsnumber, {}))

    return result


def parse_session_list(raw: bytes) -> list[str]:
    parser = etree.XMLParser(resolve_entities=False)
    namespace = {"ns": "http://www.beyondtrust.com/sra/namespaces/API/reporting"}

    root = etree.fromstring(raw, parser=parser)
    lsids = root.xpath("//ns:session_summary/@lsid", namespaces=namespace)
    return lsids


def parse_session_end_time(raw: bytes) -> int:
    parser = etree.XMLParser(resolve_entities=False)
    namespace = {"ns": "http://www.beyondtrust.com/sra/namespaces/API/reporting"}

    root = etree.fromstring(raw, parser=parser)
    end_time_elem = root.xpath("/ns:session_list/ns:session/ns:end_time/@timestamp", namespaces=namespace)
    return int(end_time_elem[0])


def parse_session(raw: bytes) -> list[dict[str, Any]]:
    parser = etree.XMLParser(resolve_entities=False)
    namespace = {"ns": "http://www.beyondtrust.com/sra/namespaces/API/reporting"}

    root = etree.fromstring(raw, parser=parser)
    participants = _parse_participants(root, namespace)

    events_header: dict[str, Any] = {
        "session_id": root.xpath("/ns:session_list/ns:session/@lsid", namespaces=namespace)[0],
        "jump_group": {
            "name": root.xpath("/ns:session_list/ns:session/ns:jump_group/text()", namespaces=namespace)[0],
            "type": root.xpath("/ns:session_list/ns:session/ns:jump_group/@type", namespaces=namespace)[0],
        },
    }

    for tag in ("primary_customer", "primary_rep"):
        primary = _parse_primary_participant(root, tag, participants, namespace)
        if primary:
            events_header[tag] = primary

    for counter in SESSION_COUNTERS:
        values = root.xpath(f"/ns:session_list/ns:session/ns:{counter}/text()", namespaces=namespace)
        if values:
            events_header[counter] = values[0]

    result = []
    events = root.xpath("/ns:session_list/ns:session/ns:session_details/ns:event", namespaces=namespace)
    for event in events:
        event_record = {
            "timestamp": event.attrib["timestamp"],
            "event_type": event.attrib["event_type"],
        }

        performed_by_elem = event.find("ns:performed_by", namespaces=namespace)
        data_elem = event.find("ns:data", namespaces=namespace)
        destination_elem = event.find("ns:destination", namespaces=namespace)

        if performed_by_elem is not None:
            event_record["performed_by"] = _describe_element(performed_by_elem, participants)

        if data_elem is not None:
            event_data = {}
            for item in data_elem:
                event_data[item.attrib["name"]] = item.attrib["value"]

            event_record["data"] = event_data

        if destination_elem is not None:
            event_record["destination"] = _describe_element(destination_elem)

        event_record.update(events_header)
        result.append(event_record)

    return result


def parse_vault_activity(raw: bytes) -> list[dict[str, Any]]:
    parser = etree.XMLParser(resolve_entities=False)
    namespace = {"ns": "http://www.beyondtrust.com/sra/namespaces/API/reporting"}

    root = etree.fromstring(raw, parser=parser)

    result = []
    events = root.xpath("/ns:vault_account_activity_list/ns:vault_account_activity", namespaces=namespace)
    for event in events:
        event_record = {
            "timestamp": event.attrib["timestamp"],
            "account_id": event.attrib["account"],
            "event_type": event.attrib["event_type"],
        }

        data_elem = event.find("ns:data", namespaces=namespace)
        if data_elem is not None:
            event_record["data"] = data_elem.text

        performed_by_elem = event.find("ns:performed_by", namespaces=namespace)

        if performed_by_elem is not None:
            event_record["performed_by"] = {
                "id": performed_by_elem.attrib["id"],
                "type": performed_by_elem.attrib["type"],
                "name": performed_by_elem.text,
            }

        result.append(event_record)

    return result


def parse_team(raw: bytes) -> list[dict[str, Any]]:
    parser = etree.XMLParser(resolve_entities=False)
    namespace = {"ns": "http://www.beyondtrust.com/sra/namespaces/API/reporting"}

    root = etree.fromstring(raw, parser=parser)

    result = []
    team_activities = root.xpath("/ns:team_activity_list/ns:team_activity", namespaces=namespace)
    for team_activity in team_activities:
        team_id = team_activity.attrib.get("id")
        team_name = team_activity.attrib.get("name")

        events = team_activity.xpath("./ns:events/ns:event", namespaces=namespace)
        for event in events:
            event_record = {
                "timestamp": event.attrib["timestamp"],
                "team": {
                    "id": team_id,
                    "name": team_name,
                },
                "performed_by": {},
                "event_type": event.attrib.get("event_type"),
                "data": {},
            }

            performed_by_elem = event.find("ns:performed_by", namespaces=namespace)
            if performed_by_elem is not None:
                event_record["performed_by"] = {
                    "type": performed_by_elem.attrib["type"],
                    "name": performed_by_elem.text,
                }

            data_elem = event.xpath("./ns:data/ns:value", namespaces=namespace)
            for item in data_elem:
                event_record["data"][item.attrib["name"]] = item.attrib["value"]

            result.append(event_record)

    return result
