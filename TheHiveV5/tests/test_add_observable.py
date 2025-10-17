from typing import Any, Optional, List
import requests_mock

from thehive.add_observable import TheHiveCreateObservableV5
from thehive4py.types.observable import OutputObservable

SEKOIA_BASE_URL: str = "https://app.sekoia.io"

ALERT_ID: str = "~40964304"

EVENTS: list[dict[str, Any]] = [
    {
        "message": "1726504602.384 5756 192.168.0.1 TCP_TUNNEL/200 6295 CONNECT www.binance.com:443 - HIER_DIRECT/api42-api.example.com -",
        "event.id": "aa837318-89ed-486e-b213-2c8aa705f1b2",
        "source.ip": "192.168.0.1",
        "timestamp": "2024-09-16T16:36:42.384000Z",
        "__event_id": "ZXRlcm5hbC1ldmVudHMtY2Y4ODhjNmQtZjNlYi00N2E4LWI0M2UtYjYzZTYzZWE0N2I4LTAwMDAwMTpzT2xwcEprQkh0blBaTUc1VUdjeg==",
        "related.ip": "192.168.0.1",
        "event.created": "2025-10-02T10:12:25.368672+00:00",
        "observer.type": "proxy",
        "related.hosts": [
            "www.binance.com",
            "api42-api.example.com",
            "binance.com"
        ],
        "server.domain": "api42-api.example.com",
        "event.category": [
            "network",
            "web"
        ],
        "event.duration": 5756,
        "source.address": "192.168.0.1",
        "alert_short_ids": [
            "AL8op2E3Dr9d"
        ],
        "observer.vendor": "Squid",
        "destination.port": 443,
        "observer.product": "Squid",
        "sekoiaio.any_tag": [
            "domains_top_100_000",
            "domains_top_10_000",
            "rfc5735",
            "domains_top_1_000_000",
            "rfc1918"
        ],
        "sekoiaio.matches": [
            {
                "paths": [
                    "destination.registered_domain"
                ],
                "rule_instance_uuid": "af38297f-441e-4111-a1b7-b9b2d33c3b91",
                "rule_definition_uuid": "2bb4bbda-742b-49d7-82a2-6c8a14f3211c"
            }
        ],
        "network.direction": "egress",
        "network.transport": "tcp",
        "destination.domain": "www.binance.com",
        "destination.address": "www.binance.com",
        "http.request.method": "CONNECT",
        "http.response.bytes": 6295,
        "sekoiaio.entity.uuid": "156a53ed-e5d0-4508-8dae-748755efc62b",
        "sekoiaio.intake.uuid": "8e0d5564-5785-45b9-a828-b069ed14311a",
        "squid.hierarchy_code": "HIER_DIRECT",
        "destination.subdomain": "www",
        "sekoiaio.intake.dialect": "squid",
        "sekoiaio.tags.source.ip": [
            "rfc1918",
            "rfc5735"
        ],
        "sekoiaio.tags.related.ip": [
            "rfc1918",
            "rfc5735"
        ],
        "http.response.status_code": 200,
        "destination.top_level_domain": "com",
        "sekoiaio.intake.dialect_uuid": "a0dbb8f3-ca1c-4c6b-aafa-595bd430c0cb",
        "destination.registered_domain": "binance.com",
        "sekoiaio.intake.parsing_status": "success",
        "sekoiaio.customer.community_uuid": "cf888c6d-f3eb-47a8-b43e-b63e63ea47b8",
        "sekoiaio.tags.destination.registered_domain": [
            "domains_top_100_000",
            "domains_top_10_000",
            "domains_top_1_000_000"
        ]
    },
    {
        "message": "1726504602.384 5756 192.168.0.1 TCP_TUNNEL/200 6295 CONNECT www.binance.com:443 - HIER_DIRECT/api42-api.example.com -",
        "event.id": "65eea69c-1cfe-4a4c-989e-8772ea5be043",
        "source.ip": "192.168.0.1",
        "timestamp": "2024-09-16T16:36:42.384000Z",
        "__event_id": "ZXRlcm5hbC1ldmVudHMtY2Y4ODhjNmQtZjNlYi00N2E4LWI0M2UtYjYzZTYzZWE0N2I4LTAwMDAwMTpwakZwcEprQlpLakhRNE43V01DTg==",
        "related.ip": "192.168.0.1",
        "event.created": "2025-10-02T10:12:24.007348+00:00",
        "observer.type": "proxy",
        "related.hosts": [
            "www.binance.com",
            "api42-api.example.com",
            "binance.com"
        ],
        "server.domain": "api42-api.example.com",
        "event.category": [
            "network",
            "web"
        ],
        "event.duration": 5756,
        "source.address": "192.168.0.1",
        "alert_short_ids": [
            "AL8op2E3Dr9d"
        ],
        "observer.vendor": "Squid",
        "destination.port": 443,
        "observer.product": "Squid",
        "sekoiaio.any_tag": [
            "domains_top_100_000",
            "domains_top_10_000",
            "rfc5735",
            "domains_top_1_000_000",
            "rfc1918"
        ],
        "sekoiaio.matches": [
            {
                "paths": [
                    "destination.registered_domain"
                ],
                "rule_instance_uuid": "af38297f-441e-4111-a1b7-b9b2d33c3b91",
                "rule_definition_uuid": "2bb4bbda-742b-49d7-82a2-6c8a14f3211c"
            }
        ],
        "network.direction": "egress",
        "network.transport": "tcp",
        "destination.domain": "www.binance.com",
        "destination.address": "www.binance.com",
        "http.request.method": "CONNECT",
        "http.response.bytes": 6295,
        "sekoiaio.entity.uuid": "156a53ed-e5d0-4508-8dae-748755efc62b",
        "sekoiaio.intake.uuid": "8e0d5564-5785-45b9-a828-b069ed14311a",
        "squid.hierarchy_code": "HIER_DIRECT",
        "destination.subdomain": "www",
        "sekoiaio.intake.dialect": "squid",
        "sekoiaio.tags.source.ip": [
            "rfc1918",
            "rfc5735"
        ],
        "sekoiaio.tags.related.ip": [
            "rfc1918",
            "rfc5735"
        ],
        "http.response.status_code": 200,
        "destination.top_level_domain": "com",
        "sekoiaio.intake.dialect_uuid": "a0dbb8f3-ca1c-4c6b-aafa-595bd430c0cb",
        "destination.registered_domain": "binance.com",
        "sekoiaio.intake.parsing_status": "success",
        "sekoiaio.customer.community_uuid": "cf888c6d-f3eb-47a8-b43e-b63e63ea47b8",
        "sekoiaio.tags.destination.registered_domain": [
            "domains_top_100_000",
            "domains_top_1_000_000",
            "domains_top_10_000"
        ]
    },
    {
        "message": "1726504602.384 5756 192.168.0.1 TCP_TUNNEL/200 6295 CONNECT www.binance.com:443 - HIER_DIRECT/api42-api.example.com -",
        "event.id": "a18e1a14-b379-450d-a51c-4938290cdbea",
        "source.ip": "192.168.0.1",
        "timestamp": "2024-09-16T16:36:42.384000Z",
        "__event_id": "ZXRlcm5hbC1ldmVudHMtY2Y4ODhjNmQtZjNlYi00N2E4LWI0M2UtYjYzZTYzZWE0N2I4LTAwMDAwMTpDd3k3cFprQnFEc0lXTnVhREJhUg==",
        "related.ip": "192.168.0.1",
        "event.created": "2025-10-02T16:21:59.043096+00:00",
        "observer.type": "proxy",
        "related.hosts": [
            "www.binance.com",
            "api42-api.example.com",
            "binance.com"
        ],
        "server.domain": "api42-api.example.com",
        "event.category": [
            "network",
            "web"
        ],
        "event.duration": 5756,
        "source.address": "192.168.0.1",
        "alert_short_ids": [
            "AL8op2E3Dr9d"
        ],
        "observer.vendor": "Squid",
        "destination.port": 443,
        "observer.product": "Squid",
        "sekoiaio.any_tag": [
            "domains_top_100_000",
            "domains_top_10_000",
            "rfc5735",
            "domains_top_1_000_000",
            "rfc1918"
        ],
        "sekoiaio.matches": [
            {
                "paths": [
                    "destination.registered_domain"
                ],
                "rule_instance_uuid": "af38297f-441e-4111-a1b7-b9b2d33c3b91",
                "rule_definition_uuid": "2bb4bbda-742b-49d7-82a2-6c8a14f3211c"
            }
        ],
        "network.direction": "egress",
        "network.transport": "tcp",
        "destination.domain": "www.binance.com",
        "destination.address": "www.binance.com",
        "http.request.method": "CONNECT",
        "http.response.bytes": 6295,
        "sekoiaio.entity.uuid": "156a53ed-e5d0-4508-8dae-748755efc62b",
        "sekoiaio.intake.uuid": "8e0d5564-5785-45b9-a828-b069ed14311a",
        "squid.hierarchy_code": "HIER_DIRECT",
        "destination.subdomain": "www",
        "sekoiaio.intake.dialect": "squid",
        "sekoiaio.tags.source.ip": [
            "rfc1918",
            "rfc5735"
        ],
        "sekoiaio.tags.related.ip": [
            "rfc1918",
            "rfc5735"
        ],
        "http.response.status_code": 200,
        "destination.top_level_domain": "com",
        "sekoiaio.intake.dialect_uuid": "a0dbb8f3-ca1c-4c6b-aafa-595bd430c0cb",
        "destination.registered_domain": "binance.com",
        "sekoiaio.intake.parsing_status": "success",
        "sekoiaio.customer.community_uuid": "cf888c6d-f3eb-47a8-b43e-b63e63ea47b8",
        "sekoiaio.tags.destination.registered_domain": [
            "domains_top_10_000",
            "domains_top_1_000_000",
            "domains_top_100_000"
        ]
    },
    {
        "message": "1726504602.384 5756 192.168.0.1 TCP_TUNNEL/200 6295 CONNECT www.binance.com:443 - HIER_DIRECT/api42-api.example.com -",
        "event.id": "c1c81774-eeb8-4fd4-992a-cb2633dc08fd",
        "source.ip": "192.168.0.1",
        "timestamp": "2024-09-16T16:36:42.384000Z",
        "__event_id": "ZXRlcm5hbC1ldmVudHMtY2Y4ODhjNmQtZjNlYi00N2E4LWI0M2UtYjYzZTYzZWE0N2I4LTAwMDAwMTozeS0zcFprQmQ5aGp2ZDY1N3NqMA==",
        "related.ip": "192.168.0.1",
        "event.created": "2025-10-02T16:18:32.758885+00:00",
        "observer.type": "proxy",
        "related.hosts": [
            "www.binance.com",
            "api42-api.example.com",
            "binance.com"
        ],
        "server.domain": "api42-api.example.com",
        "event.category": [
            "network",
            "web"
        ],
        "event.duration": 5756,
        "source.address": "192.168.0.1",
        "alert_short_ids": [
            "AL8op2E3Dr9d"
        ],
        "observer.vendor": "Squid",
        "destination.port": 443,
        "observer.product": "Squid",
        "sekoiaio.any_tag": [
            "domains_top_100_000",
            "domains_top_10_000",
            "rfc5735",
            "domains_top_1_000_000",
            "rfc1918"
        ],
        "sekoiaio.matches": [
            {
                "paths": [
                    "destination.registered_domain"
                ],
                "rule_instance_uuid": "af38297f-441e-4111-a1b7-b9b2d33c3b91",
                "rule_definition_uuid": "2bb4bbda-742b-49d7-82a2-6c8a14f3211c"
            }
        ],
        "network.direction": "egress",
        "network.transport": "tcp",
        "destination.domain": "www.binance.com",
        "destination.address": "www.binance.com",
        "http.request.method": "CONNECT",
        "http.response.bytes": 6295,
        "sekoiaio.entity.uuid": "156a53ed-e5d0-4508-8dae-748755efc62b",
        "sekoiaio.intake.uuid": "8e0d5564-5785-45b9-a828-b069ed14311a",
        "squid.hierarchy_code": "HIER_DIRECT",
        "destination.subdomain": "www",
        "sekoiaio.intake.dialect": "squid",
        "sekoiaio.tags.source.ip": [
            "rfc5735",
            "rfc1918"
        ],
        "sekoiaio.tags.related.ip": [
            "rfc5735",
            "rfc1918"
        ],
        "http.response.status_code": 200,
        "destination.top_level_domain": "com",
        "sekoiaio.intake.dialect_uuid": "a0dbb8f3-ca1c-4c6b-aafa-595bd430c0cb",
        "destination.registered_domain": "binance.com",
        "sekoiaio.intake.parsing_status": "success",
        "sekoiaio.customer.community_uuid": "cf888c6d-f3eb-47a8-b43e-b63e63ea47b8",
        "sekoiaio.tags.destination.registered_domain": [
            "domains_top_1_000_000",
            "domains_top_100_000",
            "domains_top_10_000"
        ]
    },
    {
        "message": "1726504602.384 5756 192.168.0.1 TCP_TUNNEL/200 6295 CONNECT www.binance.com:443 - HIER_DIRECT/api42-api.example.com -",
        "event.id": "45f4428a-594a-4b8d-aee6-3e061a3a007c",
        "source.ip": "192.168.0.1",
        "timestamp": "2024-09-16T16:36:42.384000Z",
        "__event_id": "ZXRlcm5hbC1ldmVudHMtY2Y4ODhjNmQtZjNlYi00N2E4LWI0M2UtYjYzZTYzZWE0N2I4LTAwMDAwMTotVEZ4cEprQlpLakhRNE43OTlCZg==",
        "related.ip": "192.168.0.1",
        "event.created": "2025-10-02T09:38:21.028626+00:00",
        "observer.type": "proxy",
        "related.hosts": [
            "www.binance.com",
            "api42-api.example.com",
            "binance.com"
        ],
        "server.domain": "api42-api.example.com",
        "event.category": [
            "network",
            "web"
        ],
        "event.duration": 5756,
        "source.address": "192.168.0.1",
        "alert_short_ids": [
            "AL8op2E3Dr9d"
        ],
        "observer.vendor": "Squid",
        "destination.port": 443,
        "observer.product": "Squid",
        "sekoiaio.any_tag": [
            "domains_top_100_000",
            "domains_top_10_000",
            "rfc5735",
            "domains_top_1_000_000",
            "rfc1918"
        ],
        "sekoiaio.matches": [
            {
                "paths": [
                    "destination.registered_domain"
                ],
                "rule_instance_uuid": "af38297f-441e-4111-a1b7-b9b2d33c3b91",
                "rule_definition_uuid": "2bb4bbda-742b-49d7-82a2-6c8a14f3211c"
            }
        ],
        "network.direction": "egress",
        "network.transport": "tcp",
        "destination.domain": "www.binance.com",
        "destination.address": "www.binance.com",
        "http.request.method": "CONNECT",
        "http.response.bytes": 6295,
        "sekoiaio.entity.uuid": "156a53ed-e5d0-4508-8dae-748755efc62b",
        "sekoiaio.intake.uuid": "8e0d5564-5785-45b9-a828-b069ed14311a",
        "squid.hierarchy_code": "HIER_DIRECT",
        "destination.subdomain": "www",
        "sekoiaio.intake.dialect": "squid",
        "sekoiaio.tags.source.ip": [
            "rfc5735",
            "rfc1918"
        ],
        "sekoiaio.tags.related.ip": [
            "rfc5735",
            "rfc1918"
        ],
        "http.response.status_code": 200,
        "destination.top_level_domain": "com",
        "sekoiaio.intake.dialect_uuid": "a0dbb8f3-ca1c-4c6b-aafa-595bd430c0cb",
        "destination.registered_domain": "binance.com",
        "sekoiaio.intake.parsing_status": "success",
        "sekoiaio.customer.community_uuid": "cf888c6d-f3eb-47a8-b43e-b63e63ea47b8",
        "sekoiaio.tags.destination.registered_domain": [
            "domains_top_1_000_000",
            "domains_top_100_000",
            "domains_top_10_000"
        ]
    }
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
HIVE_OUTPUT: Optional[OutputObservable] = [
    {
        "_id": "~40964152",
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
        "_id": "~40968200",
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
        "_id": "~81924184",
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
    }

    with requests_mock.Mocker() as mock_requests:
        #mock_requests.post(url="https://thehive-project.org/api/v1/alert/{ALERT_ID}/observable", status_code=200, json=HIVE_OUTPUT)
        url = f"https://thehive-project.org/api/v1/alert/{ALERT_ID}/observable"
        mock_requests.post(url=url, status_code=200, json=HIVE_OUTPUT)

        result: List[OutputObservable] = action.run({"alert_id": ALERT_ID, "events": EVENTS})
        assert result is not None
        # Assert that there is a result with dataType == "domain" and data == "www.binance.com"
        # OutputObservable is likely a Dict[str, Any], so .get is valid
        # Flatten result if it is a list of lists
        flat_result = [item for sublist in result for item in (sublist if isinstance(sublist, list) else [sublist])]
        assert any(obs["dataType"] == "domain" and obs["data"] == "www.binance.com" for obs in flat_result)
        assert any(obs["dataType"] == "ip" and obs["data"] == "192.168.0.1" for obs in flat_result)


def test_add_observables_action_api_error(requests_mock):
    #mock_alert = requests_mock.post(url="https://thehive-project.org/api/v1/alert/{ALERT_ID}/observable", status_code=500)
    url = f"https://thehive-project.org/api/v1/alert/{ALERT_ID}/observable"
    mock_alert = requests_mock.post(url=url, status_code=500)

    action = TheHiveCreateObservableV5()
    action.module.configuration = {
        "base_url": "https://thehive-project.org",
        "apikey": "LOREM",
        "organisation": "SEKOIA",
    }

    result = action.run({"alert_id": ALERT_ID, "events": EVENTS})

    assert not result
    assert mock_alert.call_count == 1
