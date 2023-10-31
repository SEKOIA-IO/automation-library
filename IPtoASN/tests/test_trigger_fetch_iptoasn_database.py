import pytest
import requests_mock

from iptoasn.trigger_fetch_iptoasn_database import TriggerFetchIPtoASNDatabase


@pytest.fixture(autouse=True)
def request_mock():
    with requests_mock.mock() as m:
        yield m


@pytest.fixture
def trigger(symphony_storage, request_mock, config_storage):
    trigger = TriggerFetchIPtoASNDatabase(data_path=symphony_storage)
    trigger.configuration = {"interval": 0, "chunk_size": 5}
    trigger._token = "token"
    config_storage.joinpath(TriggerFetchIPtoASNDatabase.CALLBACK_URL_FILE_NAME).write_text("https://callback.url/")
    request_mock.post(trigger.callback_url)
    request_mock.post(trigger.logs_url)
    yield trigger


def test_get_iptoasn_database(trigger, symphony_storage, request_mock):
    with open("tests/data/ip2asn-combined.tsv.gz", "rb") as mock_fp:
        for url in trigger.database_urls:
            request_mock.get(
                url,
                content=mock_fp.read(),
            )
        assert trigger._fetch_database() is None
        assert request_mock.called
        caller_params = request_mock.request_history[1].json()
        assert "name" in caller_params and caller_params["name"] == "IPTOASN List Chunk 0-7"
        assert "event" in caller_params
        assert "directory" in caller_params


def test_parse_db_rows_ipv4(trigger, mocked_uuid):
    # simple ipv4 segment
    assert list(
        trigger._parse_db_row(
            b"192.168.0.0	192.168.0.255	2519	JP	VECTANT ARTERIA Networks Corporation\n",
            tag_valid_from="2020-05-29T20:37:43.010966Z",
            tag_valid_until="2020-05-30T06:37:43.010966Z",
            asn_cache=dict(),
        )
    ) == [
        [
            {
                "id": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "name": "VECTANT ARTERIA Networks Corporation",
                "number": 2519,
                "type": "autonomous-system",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "country:JP",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    }
                ],
            },
            {
                "id": "observable-relationship--00000000-0000-0000-0000-000000000000",
                "relationship_type": "belongs-to",
                "source_ref": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "target_ref": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "type": "observable-relationship",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
            },
            {
                "id": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "type": "ipv4-addr",
                "value": "192.168.0.0/24",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "country:JP",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                    {
                        "name": "asn:2519",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                ],
            },
        ]
    ]

    # complex ipv4 segment
    assert list(
        trigger._parse_db_row(
            b"192.168.0.2	192.168.0.10	2519	jp	VECTANT ARTERIA Networks Corporation\n",
            tag_valid_from="2020-05-29T20:37:43.010966Z",
            tag_valid_until="2020-05-30T06:37:43.010966Z",
            asn_cache=dict(),
        )
    ) == [
        [
            {
                "id": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "name": "VECTANT ARTERIA Networks Corporation",
                "number": 2519,
                "type": "autonomous-system",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "country:JP",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    }
                ],
            },
            {
                "id": "observable-relationship--00000000-0000-0000-0000-000000000000",
                "relationship_type": "belongs-to",
                "source_ref": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "target_ref": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "type": "observable-relationship",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
            },
            {
                "id": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "type": "ipv4-addr",
                "value": "192.168.0.2/31",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "country:JP",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                    {
                        "name": "asn:2519",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                ],
            },
            {
                "id": "observable-relationship--00000000-0000-0000-0000-000000000000",
                "relationship_type": "belongs-to",
                "source_ref": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "target_ref": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "type": "observable-relationship",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
            },
            {
                "id": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "type": "ipv4-addr",
                "value": "192.168.0.4/30",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "country:JP",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                    {
                        "name": "asn:2519",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                ],
            },
            {
                "id": "observable-relationship--00000000-0000-0000-0000-000000000000",
                "relationship_type": "belongs-to",
                "source_ref": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "target_ref": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "type": "observable-relationship",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
            },
            {
                "id": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "type": "ipv4-addr",
                "value": "192.168.0.8/31",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "country:JP",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                    {
                        "name": "asn:2519",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                ],
            },
            {
                "id": "observable-relationship--00000000-0000-0000-0000-000000000000",
                "relationship_type": "belongs-to",
                "source_ref": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "target_ref": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "type": "observable-relationship",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
            },
            {
                "id": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "type": "ipv4-addr",
                "value": "192.168.0.10/32",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "country:JP",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                    {
                        "name": "asn:2519",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                ],
            },
        ]
    ]


def test_parse_db_rows_ipv6(trigger, mocked_uuid):
    # simple ipv6 segment
    assert list(
        trigger._parse_db_row(
            (
                b"2001:db8:0000:0000:0000:0000:0000:0001	"
                b"2001:db8:0000:0000:0000:0000:0000:0001	"
                b"2519	JP	VECTANT ARTERIA Networks Corporation\n"
            ),
            tag_valid_from="2020-05-29T20:37:43.010966Z",
            tag_valid_until="2020-05-30T06:37:43.010966Z",
            asn_cache=dict(),
        )
    ) == [
        [
            {
                "id": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "name": "VECTANT ARTERIA Networks Corporation",
                "number": 2519,
                "type": "autonomous-system",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "country:JP",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    }
                ],
            },
            {
                "id": "observable-relationship--00000000-0000-0000-0000-000000000000",
                "source_ref": "ipv6-addr--00000000-0000-0000-0000-000000000000",
                "target_ref": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "type": "observable-relationship",
                "relationship_type": "belongs-to",
            },
            {
                "id": "ipv6-addr--00000000-0000-0000-0000-000000000000",
                "type": "ipv6-addr",
                "value": "2001:db8::1/128",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "country:JP",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                    {
                        "name": "asn:2519",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                ],
            },
        ]
    ]

    assert list(
        trigger._parse_db_row(
            (
                b"fd34:fe56:7891:2f3a:0:0:0:0	"
                b"fd34:fe56:7891:2f3a:ffff:ffff:ffff:ffff	2519	"
                b"JP	VECTANT ARTERIA Networks Corporation\n"
            ),
            tag_valid_from="2020-05-29T20:37:43.010966Z",
            tag_valid_until="2020-05-30T06:37:43.010966Z",
            asn_cache=dict(),
        )
    ) == [
        [
            {
                "id": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "name": "VECTANT ARTERIA Networks Corporation",
                "number": 2519,
                "type": "autonomous-system",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "country:JP",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    }
                ],
            },
            {
                "id": "observable-relationship--00000000-0000-0000-0000-000000000000",
                "source_ref": "ipv6-addr--00000000-0000-0000-0000-000000000000",
                "target_ref": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "type": "observable-relationship",
                "relationship_type": "belongs-to",
            },
            {
                "id": "ipv6-addr--00000000-0000-0000-0000-000000000000",
                "type": "ipv6-addr",
                "value": "fd34:fe56:7891:2f3a::/64",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "country:JP",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                    {
                        "name": "asn:2519",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    },
                ],
            },
        ]
    ]


def test_parse_db_invalid_rows(trigger, mocked_uuid):
    assert (
        list(
            trigger._parse_db_row(
                b"invalid row",
                tag_valid_from="2020-05-29T20:37:43.010966Z",
                tag_valid_until="2020-05-30T06:37:43.010966Z",
                asn_cache=dict(),
            )
        )
        == []
    )

    # missing one field
    assert (
        list(
            trigger._parse_db_row(
                b"1.0.16.255	2519	JP	VECTANT ARTERIA Networks Corporation\n",
                tag_valid_from="2020-05-29T20:37:43.010966Z",
                tag_valid_until="2020-05-30T06:37:43.010966Z",
                asn_cache=dict(),
            )
        )
        == []
    )

    # invalid asn number
    assert (
        list(
            trigger._parse_db_row(
                b"1.0.16.0	1.0.16.255	2s519	JP	VECTANT ARTERIA Networks Corporation\n",
                tag_valid_from="2020-05-29T20:37:43.010966Z",
                tag_valid_until="2020-05-30T06:37:43.010966Z",
                asn_cache=dict(),
            )
        )
        == []
    )

    # no ASN provided
    assert (
        list(
            trigger._parse_db_row(
                b"1.0.16.0	1.0.16.255	0	JP	VECTANT ARTERIA Networks Corporation\n",
                tag_valid_from="2020-05-29T20:37:43.010966Z",
                tag_valid_until="2020-05-30T06:37:43.010966Z",
                asn_cache=dict(),
            )
        )
        == []
    )

    # unknown country
    # The country tag is not set
    assert list(
        trigger._parse_db_row(
            b"1.0.16.0	1.0.16.255	2519	XX	VECTANT ARTERIA Networks Corporation\n",
            tag_valid_from="2020-05-29T20:37:43.010966Z",
            tag_valid_until="2020-05-30T06:37:43.010966Z",
            asn_cache=dict(),
        )
    ) == [
        [
            {
                "id": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "name": "VECTANT ARTERIA Networks Corporation",
                "number": 2519,
                "type": "autonomous-system",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [],
            },
            {
                "id": "observable-relationship--00000000-0000-0000-0000-000000000000",
                "relationship_type": "belongs-to",
                "source_ref": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "target_ref": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "type": "observable-relationship",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
            },
            {
                "id": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "type": "ipv4-addr",
                "value": "1.0.16.0/24",
                "x_inthreat_sources_refs": ["identity--9b3b35de-7606-4644-84be-3c68da7d3b99"],
                "x_inthreat_tags": [
                    {
                        "name": "asn:2519",
                        "valid_from": "2020-05-29T20:37:43.010966Z",
                        "valid_until": "2020-05-30T06:37:43.010966Z",
                    }
                ],
            },
        ]
    ]

    # invalid ip start
    assert (
        list(
            trigger._parse_db_row(
                b"1.a.16.0	1.0.16.255	2519	JP	VECTANT ARTERIA Networks Corporation\n",
                tag_valid_from="2020-05-29T20:37:43.010966Z",
                tag_valid_until="2020-05-30T06:37:43.010966Z",
                asn_cache=dict(),
            )
        )
        == []
    )

    # invalid ip end
    assert (
        list(
            trigger._parse_db_row(
                b"1.0.16.0	2001:0db8:0000:85a3:0000:0000:ac1f:8001	2519	JP	VECTANT ARTERIA Networks Corporation\n",
                tag_valid_from="2020-05-29T20:37:43.010966Z",
                tag_valid_until="2020-05-30T06:37:43.010966Z",
                asn_cache=dict(),
            )
        )
        == []
    )
