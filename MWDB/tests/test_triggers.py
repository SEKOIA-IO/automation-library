from unittest.mock import Mock

import pytest
import requests_mock

from mwdb_module.triggers import MWDBConfigsTrigger
from tests.data import config_details, configs, file_details


@pytest.fixture
def trigger():
    trigger = MWDBConfigsTrigger()
    trigger.module.configuration = {
        "api_key": "eyJhbGciOiJIUzUxMiJ9"
        ".eyJsb2dpbiI6ImZvbyIsImFwaV9rZXlfaWQiOiJlNjk3ZTc4ZC02MTU5LTRjMmEtODdlMC0xZmRmMjNmZWFlZjIifQ"
        ".3f2XsXVR7Y5sPTighfPqSf068usSSjaIwQymBHM12jBoJX6eg30uoAh5vgm-JpMDTQMy0uDzcFwQ_EHgT8kvJA"
    }
    trigger.listen = trigger.client.recent_configs  # change it to avoid running forever
    trigger.send_event = Mock()
    trigger.log = Mock()
    return trigger


@pytest.fixture
def mwdb_mock():
    with requests_mock.Mocker() as m:
        m.get(
            "https://mwdb.cert.pl/api/config",
            [{"json": configs}, {"json": {"configs": []}}],
        )
        m.get(
            "https://mwdb.cert.pl/api/config/5cbdbf9b8c8e3441b1a460a641d413c18a39fa10924c20dca2cffd2d303b4067",
            json=config_details,
        )
        m.get(
            "https://mwdb.cert.pl/api/file/14a64be54a3af66d3ee626a2b57bef40031c1b2b2ee4682e64a0d5d4a761c0fc",
            json=file_details,
        )
        yield m


def test_run(trigger, mwdb_mock):
    trigger.run()

    trigger.send_event.assert_called
    assert trigger.send_event.call_count == 1
    name = trigger.send_event.call_args[0][0]
    config = trigger.send_event.call_args[0][1]

    assert "files" in config
    assert len(config["files"]) > 0
    for f in config["files"]:
        assert "md5" in f
        assert "file_name" in f
        assert "sha256" in f

    assert name == "MWDB config: trickbot (static)"
    assert config["config_type"] == "static"
    assert config["family"] == "trickbot"
    assert config["cfg"]["botnet"] == "lib699"
    assert "config" not in config
