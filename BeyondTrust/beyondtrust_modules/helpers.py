from typing import Any

from lxml import etree


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
    events_header = {
        "session_id": root.xpath("/ns:session_list/ns:session/@lsid", namespaces=namespace)[0],
        "jump_group": {
            "name": root.xpath("/ns:session_list/ns:session/ns:jump_group/text()", namespaces=namespace)[0],
            "type": root.xpath("/ns:session_list/ns:session/ns:jump_group/@type", namespaces=namespace)[0],
        },
    }

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
            event_record["performed_by"] = {
                "type": performed_by_elem.attrib["type"],
                "name": performed_by_elem.text,
            }

        if data_elem is not None:
            event_data = {}
            for item in data_elem:
                event_data[item.attrib["name"]] = item.attrib["value"]

            event_record["data"] = event_data

        if destination_elem is not None:
            event_record["destination"] = {
                "type": destination_elem.attrib["type"],
                "name": destination_elem.text,
            }

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
                "timestamp": event.attrib.get("timestamp"),
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
            if data_elem is not None:
                for item in data_elem:
                    event_record["data"][item.attrib["name"]] = item.attrib["value"]

            result.append(event_record)

    return result
