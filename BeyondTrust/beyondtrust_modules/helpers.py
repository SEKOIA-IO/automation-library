from typing import Any

from lxml import etree


def parse_session_list(raw: bytes) -> list[str]:
    namespace = {"ns": "http://www.beyondtrust.com/sra/namespaces/API/reporting"}
    root = etree.fromstring(raw)
    lsids = root.xpath("//ns:session_summary/@lsid", namespaces=namespace)
    return lsids


def parse_session_end_time(raw: bytes) -> int:
    namespace = {"ns": "http://www.beyondtrust.com/sra/namespaces/API/reporting"}

    root = etree.fromstring(raw)
    end_time_elem = root.xpath("/ns:session_list/ns:session/ns:end_time/@timestamp", namespaces=namespace)
    return int(end_time_elem[0])


def parse_session(raw: bytes) -> list[dict[str, Any]]:
    namespace = {"ns": "http://www.beyondtrust.com/sra/namespaces/API/reporting"}

    root = etree.fromstring(raw)
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
