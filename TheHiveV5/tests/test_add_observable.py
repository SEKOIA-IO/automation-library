from typing import Any, Optional, List
import json
import pytest
import requests_mock

from thehive.add_observable import TheHiveCreateObservableV5
from thehive4py.types.observable import OutputObservable
from thehive4py.errors import TheHiveError

SEKOIA_BASE_URL: str = "https://app.sekoia.io"

ALERT_ID: str = "~00000001"

EVENTS: list[dict[str, Any]] = [
    {
        "message": "1726504602.384 5756 192.168.0.1 TCP_TUNNEL/200 6295 CONNECT www.binance.com:443 - HIER_DIRECT/api42-api.example.com -",
        "event.id": "00000000-0000-0000-0000-000000000000",
        "source.ip": "192.168.0.1",
        "timestamp": "2024-09-16T16:36:42.384000Z",
        "__event_id": "REDACTED_BASE64_EVENT_ID_001",
        "related.ip": "192.168.0.1",
        "event.created": "2025-10-02T10:12:25.368672+00:00",
        "observer.type": "proxy",
        "related.hosts": ["www.binance.com", "api42-api.example.com", "binance.com"],
        "server.domain": "api42-api.example.com",
        "event.category": ["network", "web"],
        "event.duration": 5756,
        "source.address": "192.168.0.1",
        "alert_short_ids": ["ALXXXXXXXX"],
        "observer.vendor": "Squid",
        "destination.port": 443,
        "observer.product": "Squid",
        "sekoiaio.any_tag": [
            "domains_top_100_000",
            "domains_top_10_000",
            "rfc5735",
            "domains_top_1_000_000",
            "rfc1918",
        ],
        "sekoiaio.matches": [
            {
                "paths": ["destination.registered_domain"],
                "rule_instance_uuid": "00000000-0000-0000-0000-000000000002",
                "rule_definition_uuid": "00000000-0000-0000-0000-000000000003",
            }
        ],
        "network.direction": "egress",
        "network.transport": "tcp",
        "destination.domain": "www.binance.com",
        "destination.address": "www.binance.com",
        "http.request.method": "CONNECT",
        "http.response.bytes": 6295,
        "sekoiaio.entity.uuid": "00000000-0000-0000-0000-000000000004",
        "sekoiaio.intake.uuid": "00000000-0000-0000-0000-0000000000005",
        "squid.hierarchy_code": "HIER_DIRECT",
        "destination.subdomain": "www",
        "sekoiaio.intake.dialect": "squid",
        "sekoiaio.tags.source.ip": ["rfc1918", "rfc5735"],
        "sekoiaio.tags.related.ip": ["rfc1918", "rfc5735"],
        "http.response.status_code": 200,
        "destination.top_level_domain": "com",
        "sekoiaio.intake.dialect_uuid": "00000000-0000-0000-0000-0000000000006",
        "destination.registered_domain": "binance.com",
        "sekoiaio.intake.parsing_status": "success",
        "sekoiaio.customer.community_uuid": "00000000-0000-0000-0000-000000000008",
        "sekoiaio.tags.destination.registered_domain": [
            "domains_top_100_000",
            "domains_top_10_000",
            "domains_top_1_000_000",
        ],
    },
    {
        "message": "1726504602.384 5756 192.168.0.1 TCP_TUNNEL/200 6295 CONNECT www.binance.com:443 - HIER_DIRECT/api42-api.example.com -",
        "event.id": "00000000-0000-0000-0000-000000000011",
        "source.ip": "192.168.0.1",
        "timestamp": "2024-09-16T16:36:42.384000Z",
        "__event_id": "REDACTED_BASE64_EVENT_ID_002",
        "related.ip": "192.168.0.1",
        "event.created": "2025-10-02T10:12:24.007348+00:00",
        "observer.type": "proxy",
        "related.hosts": ["www.binance.com", "api42-api.example.com", "binance.com"],
        "server.domain": "api42-api.example.com",
        "event.category": ["network", "web"],
        "event.duration": 5756,
        "source.address": "192.168.0.1",
        "alert_short_ids": ["ALXXXXXXXXX"],
        "observer.vendor": "Squid",
        "destination.port": 443,
        "observer.product": "Squid",
        "sekoiaio.any_tag": [
            "domains_top_100_000",
            "domains_top_10_000",
            "rfc5735",
            "domains_top_1_000_000",
            "rfc1918",
        ],
        "sekoiaio.matches": [
            {
                "paths": ["destination.registered_domain"],
                "rule_instance_uuid": "00000000-0000-0000-0000-000000000002",
                "rule_definition_uuid": "00000000-0000-0000-0000-000000000003",
            }
        ],
        "network.direction": "egress",
        "network.transport": "tcp",
        "destination.domain": "www.binance.com",
        "destination.address": "www.binance.com",
        "http.request.method": "CONNECT",
        "http.response.bytes": 6295,
        "sekoiaio.entity.uuid": "00000000-0000-0000-0000-000000000004",
        "sekoiaio.intake.uuid": "00000000-0000-0000-0000-000000000005",
        "squid.hierarchy_code": "HIER_DIRECT",
        "destination.subdomain": "www",
        "sekoiaio.intake.dialect": "squid",
        "sekoiaio.tags.source.ip": ["rfc1918", "rfc5735"],
        "sekoiaio.tags.related.ip": ["rfc1918", "rfc5735"],
        "http.response.status_code": 200,
        "destination.top_level_domain": "com",
        "sekoiaio.intake.dialect_uuid": "00000000-0000-0000-0000-000000000006",
        "destination.registered_domain": "binance.com",
        "sekoiaio.intake.parsing_status": "success",
        "sekoiaio.customer.community_uuid": "00000000-0000-0000-0000-000000000008",
        "sekoiaio.tags.destination.registered_domain": [
            "domains_top_100_000",
            "domains_top_1_000_000",
            "domains_top_10_000",
        ],
    },
    {
        "message": "1726504602.384 5756 192.168.0.1 TCP_TUNNEL/200 6295 CONNECT www.binance.com:443 - HIER_DIRECT/api42-api.example.com -",
        "event.id": "00000000-0000-0000-0000-000000000021",
        "source.ip": "192.168.0.1",
        "timestamp": "2024-09-16T16:36:42.384000Z",
        "__event_id": "REDACTED_BASE64_EVENT_ID_003",
        "related.ip": "192.168.0.1",
        "event.created": "2025-10-02T16:21:59.043096+00:00",
        "observer.type": "proxy",
        "related.hosts": ["www.binance.com", "api42-api.example.com", "binance.com"],
        "server.domain": "api42-api.example.com",
        "event.category": ["network", "web"],
        "event.duration": 5756,
        "source.address": "192.168.0.1",
        "alert_short_ids": ["ALXXXXXXXXX"],
        "observer.vendor": "Squid",
        "destination.port": 443,
        "observer.product": "Squid",
        "sekoiaio.any_tag": [
            "domains_top_100_000",
            "domains_top_10_000",
            "rfc5735",
            "domains_top_1_000_000",
            "rfc1918",
        ],
        "sekoiaio.matches": [
            {
                "paths": ["destination.registered_domain"],
                "rule_instance_uuid": "00000000-0000-0000-0000-000000000002",
                "rule_definition_uuid": "00000000-0000-0000-0000-000000000003",
            }
        ],
        "network.direction": "egress",
        "network.transport": "tcp",
        "destination.domain": "www.binance.com",
        "destination.address": "www.binance.com",
        "http.request.method": "CONNECT",
        "http.response.bytes": 6295,
        "sekoiaio.entity.uuid": "00000000-0000-0000-0000-000000000004",
        "sekoiaio.intake.uuid": "00000000-0000-0000-0000-000000000005",
        "squid.hierarchy_code": "HIER_DIRECT",
        "destination.subdomain": "www",
        "sekoiaio.intake.dialect": "squid",
        "sekoiaio.tags.source.ip": ["rfc1918", "rfc5735"],
        "sekoiaio.tags.related.ip": ["rfc1918", "rfc5735"],
        "http.response.status_code": 200,
        "destination.top_level_domain": "com",
        "sekoiaio.intake.dialect_uuid": "00000000-0000-0000-0000-000000000006",
        "destination.registered_domain": "binance.com",
        "sekoiaio.intake.parsing_status": "success",
        "sekoiaio.customer.community_uuid": "00000000-0000-0000-0000-000000000008",
        "sekoiaio.tags.destination.registered_domain": [
            "domains_top_10_000",
            "domains_top_1_000_000",
            "domains_top_100_000",
        ],
    },
    {
        "message": "1726504602.384 5756 192.168.0.1 TCP_TUNNEL/200 6295 CONNECT www.binance.com:443 - HIER_DIRECT/api42-api.example.com -",
        "event.id": "00000000-0000-0000-0000-000000000031",
        "source.ip": "192.168.0.1",
        "timestamp": "2024-09-16T16:36:42.384000Z",
        "__event_id": "REDACTED_BASE64_EVENT_ID_004",
        "related.ip": "192.168.0.1",
        "event.created": "2025-10-02T16:18:32.758885+00:00",
        "observer.type": "proxy",
        "related.hosts": ["www.binance.com", "api42-api.example.com", "binance.com"],
        "server.domain": "api42-api.example.com",
        "event.category": ["network", "web"],
        "event.duration": 5756,
        "source.address": "192.168.0.1",
        "alert_short_ids": ["ALXXXXXXXXX"],
        "observer.vendor": "Squid",
        "destination.port": 443,
        "observer.product": "Squid",
        "sekoiaio.any_tag": [
            "domains_top_100_000",
            "domains_top_10_000",
            "rfc5735",
            "domains_top_1_000_000",
            "rfc1918",
        ],
        "sekoiaio.matches": [
            {
                "paths": ["destination.registered_domain"],
                "rule_instance_uuid": "00000000-0000-0000-0000-000000000002",
                "rule_definition_uuid": "00000000-0000-0000-0000-000000000003",
            }
        ],
        "network.direction": "egress",
        "network.transport": "tcp",
        "destination.domain": "www.binance.com",
        "destination.address": "www.binance.com",
        "http.request.method": "CONNECT",
        "http.response.bytes": 6295,
        "sekoiaio.entity.uuid": "00000000-0000-0000-0000-000000000004",
        "sekoiaio.intake.uuid": "00000000-0000-0000-0000-000000000005",
        "squid.hierarchy_code": "HIER_DIRECT",
        "destination.subdomain": "www",
        "sekoiaio.intake.dialect": "squid",
        "sekoiaio.tags.source.ip": ["rfc5735", "rfc1918"],
        "sekoiaio.tags.related.ip": ["rfc5735", "rfc1918"],
        "http.response.status_code": 200,
        "destination.top_level_domain": "com",
        "sekoiaio.intake.dialect_uuid": "00000000-0000-0000-0000-000000000006",
        "destination.registered_domain": "binance.com",
        "sekoiaio.intake.parsing_status": "success",
        "sekoiaio.customer.community_uuid": "00000000-0000-0000-0000-000000000008",
        "sekoiaio.tags.destination.registered_domain": [
            "domains_top_1_000_000",
            "domains_top_100_000",
            "domains_top_10_000",
        ],
    },
    {
        "message": "1726504602.384 5756 192.168.0.1 TCP_TUNNEL/200 6295 CONNECT www.binance.com:443 - HIER_DIRECT/api42-api.example.com -",
        "event.id": "00000000-0000-0000-0000-000000000041",
        "source.ip": "192.168.0.1",
        "timestamp": "2024-09-16T16:36:42.384000Z",
        "__event_id": "REDACTED_BASE64_EVENT_ID_005",
        "related.ip": "192.168.0.1",
        "event.created": "2025-10-02T09:38:21.028626+00:00",
        "observer.type": "proxy",
        "related.hosts": ["www.binance.com", "api42-api.example.com", "binance.com"],
        "server.domain": "api42-api.example.com",
        "event.category": ["network", "web"],
        "event.duration": 5756,
        "source.address": "192.168.0.1",
        "alert_short_ids": ["ALXXXXXXXXX"],
        "observer.vendor": "Squid",
        "destination.port": 443,
        "observer.product": "Squid",
        "sekoiaio.any_tag": [
            "domains_top_100_000",
            "domains_top_10_000",
            "rfc5735",
            "domains_top_1_000_000",
            "rfc1918",
        ],
        "sekoiaio.matches": [
            {
                "paths": ["destination.registered_domain"],
                "rule_instance_uuid": "00000000-0000-0000-0000-000000000002",
                "rule_definition_uuid": "00000000-0000-0000-0000-000000000003",
            }
        ],
        "network.direction": "egress",
        "network.transport": "tcp",
        "destination.domain": "www.binance.com",
        "destination.address": "www.binance.com",
        "http.request.method": "CONNECT",
        "http.response.bytes": 6295,
        "sekoiaio.entity.uuid": "00000000-0000-0000-0000-000000000004",
        "sekoiaio.intake.uuid": "00000000-0000-0000-0000-000000000005",
        "squid.hierarchy_code": "HIER_DIRECT",
        "destination.subdomain": "www",
        "sekoiaio.intake.dialect": "squid",
        "sekoiaio.tags.source.ip": ["rfc5735", "rfc1918"],
        "sekoiaio.tags.related.ip": ["rfc5735", "rfc1918"],
        "http.response.status_code": 200,
        "destination.top_level_domain": "com",
        "sekoiaio.intake.dialect_uuid": "00000000-0000-0000-0000-000000000006",
        "destination.registered_domain": "binance.com",
        "sekoiaio.intake.parsing_status": "success",
        "sekoiaio.customer.community_uuid": "00000000-0000-0000-0000-000000000008",
        "sekoiaio.tags.destination.registered_domain": [
            "domains_top_1_000_000",
            "domains_top_100_000",
            "domains_top_10_000",
        ],
    },
]

HIVE_OUTPUT_ERROR = {
    "success": [],
    "failure": [
        {
            "type": "CreateError",
            "message": "Observable already exists",
            "object": {"data": "192.168.1.100"},
        },
        {
            "type": "CreateError",
            "message": "Observable already exists",
            "object": {"data": "phishing-site.com"},
        },
        {
            "type": "CreateError",
            "message": "Observable already exists",
            "object": {"data": "http://malicious.example/path"},
        },
    ],
}

# Correct HIVE_OUTPUT: single list containing three observable dicts (not multiple bracketed groups)
HIVE_OUTPUT: List[dict[str, Any]] = [
    {
        "_id": "~00000201",
        "_type": "Observable",
        "_createdBy": "testapi@thehive.local",
        "_createdAt": 1760086561186,
        "dataType": "ip",
        "data": "192.168.0.1",
        "startDate": 1760086561186,
        "tlp": 2,
        "tlpLabel": "AMBER",
        "pap": 2,
        "papLabel": "AMBER",
        "tags": [],
        "ioc": False,
        "sighted": False,
        "reports": {},
        "extraData": {},
        "ignoreSimilarity": False,
    },
    {
        "_id": "~00000202",
        "_type": "Observable",
        "_createdBy": "testapi@thehive.local",
        "_createdAt": 1760086562768,
        "dataType": "domain",
        "data": "www.binance.com",
        "startDate": 1760086562768,
        "tlp": 2,
        "tlpLabel": "AMBER",
        "pap": 2,
        "papLabel": "AMBER",
        "tags": [],
        "ioc": False,
        "sighted": False,
        "reports": {},
        "extraData": {},
        "ignoreSimilarity": False,
    },
    {
        "_id": "~00000203",
        "_type": "Observable",
        "_createdBy": "testapi@thehive.local",
        "_createdAt": 1760086564549,
        "dataType": "url",
        "data": "http://malicious.example1/path",
        "startDate": 1760086564549,
        "tlp": 2,
        "tlpLabel": "AMBER",
        "pap": 2,
        "papLabel": "AMBER",
        "tags": [],
        "ioc": False,
        "sighted": False,
        "reports": {},
        "extraData": {},
        "ignoreSimilarity": False,
    },
]


def test_add_observables_action_success():
    action = TheHiveCreateObservableV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
        "verify_certificate": False,
    }

    with requests_mock.Mocker() as mock_requests:
        # mock_requests.post(url="https://thehive-project.org/api/v1/alert/{ALERT_ID}/observable", status_code=200, json=HIVE_OUTPUT)
        url = f"https://thehive-project.org/api/v1/alert/{ALERT_ID}/observable"
        mock_requests.post(url=url, status_code=200, json=HIVE_OUTPUT)

        result = action.run({"alert_id": ALERT_ID, "events": EVENTS})
        assert result is not None
        assert isinstance(result, dict)
        assert "success" in result
        assert "failure" in result

        # Check that we have successful observables
        assert len(result["success"]) > 0

        # Flatten the success list if needed (observables may be returned in batches)
        flat_result = []
        for item in result["success"]:
            if isinstance(item, list):
                flat_result.extend(item)
            else:
                flat_result.append(item)

        # Assert that there is a result with dataType == "domain" and data == "www.binance.com"
        assert any(obs["dataType"] == "domain" and obs["data"] == "www.binance.com" for obs in flat_result)
        assert any(obs["dataType"] == "ip" and obs["data"] == "192.168.0.1" for obs in flat_result)


def test_add_observables_action_api_error(requests_mock):
    # mock_alert = requests_mock.post(url="https://thehive-project.org/api/v1/alert/{ALERT_ID}/observable", status_code=500)
    url = f"https://thehive-project.org/api/v1/alert/{ALERT_ID}/observable"
    mock_alert = requests_mock.post(url=url, status_code=500)

    action = TheHiveCreateObservableV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    # When ALL observables fail, TheHiveError should be raised
    with pytest.raises(TheHiveError):
        action.run({"alert_id": ALERT_ID, "events": EVENTS})

    # Should attempt to add each observable
    assert mock_alert.call_count > 0


def test_add_observables_action_json_decode_error():
    """Test that JSONDecodeError is properly caught and re-raised"""
    action = TheHiveCreateObservableV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    # Mock json.loads to raise JSONDecodeError
    import unittest.mock as mock

    with mock.patch("thehive.add_observable.json.loads") as mock_loads:
        mock_loads.side_effect = json.JSONDecodeError("test error", "doc", 0)

        with pytest.raises(json.JSONDecodeError):
            action.run({"alert_id": ALERT_ID, "events": EVENTS})
