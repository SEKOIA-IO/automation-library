import time
from signal import SIGINT
import os
from threading import Thread
from unittest.mock import MagicMock

import pytest
import requests_mock

from ipinfo.trigger_fetch_ipinfo_database import TriggerFetchIPInfoDatabase


@pytest.fixture(autouse=True)
def request_mock():
    with requests_mock.mock() as m:
        yield m


@pytest.fixture
def trigger(symphony_storage, request_mock, config_storage):
    module_configuration = {"api_token": "token"}
    trigger = TriggerFetchIPInfoDatabase(data_path=symphony_storage)
    trigger.configuration = {"interval": 0, "chunk_size": 10000}
    trigger.module.configuration = module_configuration
    trigger._token = "token"
    config_storage.joinpath(
        TriggerFetchIPInfoDatabase.CALLBACK_URL_FILE_NAME
    ).write_text("https://callback.url/")
    request_mock.post(trigger.callback_url)
    request_mock.post(trigger.logs_url)
    yield trigger


def test_get_interval(trigger):
    assert trigger.interval == 0


def test_get_ipinfo_database(trigger, symphony_storage, request_mock):
    with open("tests/data/country_asn.json.gz", "rb") as mock_fp:
        request_mock.get(
            trigger.database_url,
            content=mock_fp.read(),
        )
        assert trigger._fetch_database() is None
        assert request_mock.called
        caller_params = request_mock.request_history[1].json()
        assert (
            "name" in caller_params
            and caller_params["name"] == "IPINFO.IO List Chunk 0-161"
        )
        assert "event" in caller_params
        assert "directory" in caller_params


def test_parse_db_rows_ipv4(trigger, mocked_uuid):
    # ipv6 segment
    assert list(
        trigger._parse_db_row(
            row=b'{"start_ip": "2001:550:2:8::2b:1", "end_ip": "2001:550:2:8::2b:1", "country": "CA", "country_name": "Canada", "continent": "NA", "continent_name": "North America", "asn": "AS174", "as_name": "Cogent Communications", "as_domain": "cogentcomm.biz"}\n',  # noqa: E501
            tag_valid_from="2024-01-30T09:04:38Z",
            tag_valid_until="2024-01-30T09:04:38Z",
            asn_cache=dict(),
        )
    ) == [
        [
            {
                "id": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "name": "Cogent Communications",
                "number": 174,
                "type": "autonomous-system",
                "x_inthreat_sources_refs": [
                    "identity--1e9f6197-b3a0-4665-88e7-767929d013a4"
                ],
            },
            {
                "id": "observable-relationship--00000000-0000-0000-0000-000000000000",
                "relationship_type": "belongs-to",
                "source_ref": "ipv6-addr--00000000-0000-0000-0000-000000000000",
                "target_ref": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "type": "observable-relationship",
                "x_inthreat_sources_refs": [
                    "identity--1e9f6197-b3a0-4665-88e7-767929d013a4"
                ],
            },
            {
                "id": "ipv6-addr--00000000-0000-0000-0000-000000000000",
                "type": "ipv6-addr",
                "value": "2001:550:2:8::2b:1/128",
                "x_inthreat_sources_refs": [
                    "identity--1e9f6197-b3a0-4665-88e7-767929d013a4"
                ],
                "x_inthreat_tags": [
                    {
                        "name": "country:CA",
                        "valid_from": "2024-01-30T09:04:38Z",
                        "valid_until": "2024-01-30T09:04:38Z",
                    },
                    {
                        "name": "asn:174",
                        "valid_from": "2024-01-30T09:04:38Z",
                        "valid_until": "2024-01-30T09:04:38Z",
                    },
                ],
            },
        ]
    ]

    # ipv4 segment
    assert list(
        trigger._parse_db_row(
            b'{"start_ip": "38.28.1.68", "end_ip": "38.28.1.68", "country": "CZ", "country_name": "Czechia", "continent": "EU", "continent_name": "Europe", "asn": "AS174", "as_name": "Cogent Communications", "as_domain": "cogentcomm.biz"}\n',  # noqa: E501
            tag_valid_from="2024-01-30T09:11:34Z",
            tag_valid_until="2024-01-30T09:11:34Z",
            asn_cache=dict(),
        )
    ) == [
        [
            {
                "id": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "name": "Cogent Communications",
                "number": 174,
                "type": "autonomous-system",
                "x_inthreat_sources_refs": [
                    "identity--1e9f6197-b3a0-4665-88e7-767929d013a4"
                ],
            },
            {
                "id": "observable-relationship--00000000-0000-0000-0000-000000000000",
                "relationship_type": "belongs-to",
                "source_ref": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "target_ref": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "type": "observable-relationship",
                "x_inthreat_sources_refs": [
                    "identity--1e9f6197-b3a0-4665-88e7-767929d013a4"
                ],
            },
            {
                "id": "ipv4-addr--00000000-0000-0000-0000-000000000000",
                "type": "ipv4-addr",
                "value": "38.28.1.68/32",
                "x_inthreat_sources_refs": [
                    "identity--1e9f6197-b3a0-4665-88e7-767929d013a4"
                ],
                "x_inthreat_tags": [
                    {
                        "name": "country:CZ",
                        "valid_from": "2024-01-30T09:11:34Z",
                        "valid_until": "2024-01-30T09:11:34Z",
                    },
                    {
                        "name": "asn:174",
                        "valid_from": "2024-01-30T09:11:34Z",
                        "valid_until": "2024-01-30T09:11:34Z",
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


def test_run_trigger_stopped(trigger, request_mock):
    with open("tests/data/country_asn.json.gz", "rb") as mock_fp:
        request_mock.get(
            trigger.database_url,
            content=mock_fp.read(),
        )
        trigger.stop()
        try:
            trigger.run()
        except Exception:
            pytest.fail("Exception occured")
        trigger.stop()


def test_run_is_interrupted_by_signal(trigger, request_mock):
    request_mock.get(
        trigger.database_url,
        status_code=200,
    )
    pid = os.getpid()

    def set_stop_event():
        time.sleep(0.1)
        os.kill(pid, SIGINT)

    trigger.get_ipinfo_database = MagicMock()
    Thread(target=set_stop_event, daemon=True).start()
    trigger.run()
    assert len(trigger.get_ipinfo_database.mock_calls) > 0


def test_tags_valid_for(symphony_storage):
    trigger = TriggerFetchIPInfoDatabase(data_path=symphony_storage)
    trigger.configuration = {}
    assert trigger.tags_valid_for == trigger.MAX_HOUR_TAG_VALID_FOR

    trigger = TriggerFetchIPInfoDatabase(data_path=symphony_storage)
    trigger.configuration = {"tags_valid_for": 1}
    assert trigger.tags_valid_for == 1


def test_parse_db_rows_ipv4_empty_as_name(trigger, mocked_uuid):
    # ipv6 segment
    assert list(
        trigger._parse_db_row(
            row=b'{"start_ip": "2001:550:2:8::2b:1", "end_ip": "2001:550:2:8::2b:1", "country": "CA", "country_name": "Canada", "continent": "NA", "continent_name": "North America", "asn": "AS174", "as_name": "", "as_domain": "cogentcomm.biz"}\n',  # noqa: E501
            tag_valid_from="2024-01-30T09:04:38Z",
            tag_valid_until="2024-01-30T09:04:38Z",
            asn_cache=dict(),
        )
    ) == [
        [
            {
                "id": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "name": "AS174",
                "number": 174,
                "type": "autonomous-system",
                "x_inthreat_sources_refs": [
                    "identity--1e9f6197-b3a0-4665-88e7-767929d013a4"
                ],
            },
            {
                "id": "observable-relationship--00000000-0000-0000-0000-000000000000",
                "relationship_type": "belongs-to",
                "source_ref": "ipv6-addr--00000000-0000-0000-0000-000000000000",
                "target_ref": "autonomous-system--00000000-0000-0000-0000-000000000000",
                "type": "observable-relationship",
                "x_inthreat_sources_refs": [
                    "identity--1e9f6197-b3a0-4665-88e7-767929d013a4"
                ],
            },
            {
                "id": "ipv6-addr--00000000-0000-0000-0000-000000000000",
                "type": "ipv6-addr",
                "value": "2001:550:2:8::2b:1/128",
                "x_inthreat_sources_refs": [
                    "identity--1e9f6197-b3a0-4665-88e7-767929d013a4"
                ],
                "x_inthreat_tags": [
                    {
                        "name": "country:CA",
                        "valid_from": "2024-01-30T09:04:38Z",
                        "valid_until": "2024-01-30T09:04:38Z",
                    },
                    {
                        "name": "asn:174",
                        "valid_from": "2024-01-30T09:04:38Z",
                        "valid_until": "2024-01-30T09:04:38Z",
                    },
                ],
            },
        ]
    ]
