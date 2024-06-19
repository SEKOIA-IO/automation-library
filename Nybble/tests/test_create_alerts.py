import os
import time

import pytest
import requests_mock
from typing import Any

from nybble_modules.create_alert import (
    CreateAlertAction,
    CreateAlertArguments,
)


@pytest.fixture(scope="module")
def arguments():
    return CreateAlertArguments(
        alert_data={
            "uuid": "4ffec8f1-dcd2-47d9-a581-bd8929911719",
            "title": "Linux Suspicious Search",
            "created_at": 1712754356,
            "community_uuid": "7e35215c-ea51-49b2-8b20-f2417978b629",
            "urgency": {"value": 30},
            "rule": {"uuid": "8b4b4a25-3b15-47ea-b701-db75d7da7346"},
        },
        events=[
            {"host.name": "host1", "host.ip": "1.2.3.4", "timestamp": "2024-05-02T12:09:42.835000Z"},
            {"host.name": "host2", "host.ip": "5.6.7.8", "timestamp": "2024-05-02T12:09:42.835000Z"},
        ],
        rule={},
    )


SEKOIA_ALERT_RULE_MOCK_EXTRA_FIELD: dict[str, Any] = {
    "uuid": "7cb3f329-8d12-4065-8dd1-fdb91da7eecf",
    "instance_uuid": "8b4b4a25-3b15-47ea-b701-db75d7da7346",
    "event_fields": [
        {"field": "host.name", "description": "Host Name"},
        {"field": "host.ip", "description": "Host IP Address"},
        {"field": "user.name", "description": "User Name, missing in event"},
    ],
    "references": "https://abcdef.fr",
    "tags": [{"uuid": "fca4002a-07c1-41e3-8efa-c2e49a171dab", "name": "Linux"}],
    "false_positives": None,
}

SEKOIA_ALERT_RULE_MOCK: dict[str, Any] = {
    "uuid": "7cb3f329-8d12-4065-8dd1-fdb91da7eecf",
    "instance_uuid": "8b4b4a25-3b15-47ea-b701-db75d7da7346",
    "event_fields": [
        {"field": "host.name", "description": "Host Name"},
        {"field": "host.ip", "description": "Host IP Address"},
    ],
    "references": "https://abcdef.fr",
    "tags": [{"uuid": "fca4002a-07c1-41e3-8efa-c2e49a171dab", "name": "Linux"}],
    "false_positives": None,
}

SEKOIA_ALERT_RULE_MOCK_EMPTY: dict[str, Any] = {
    "uuid": "7cb3f329-8d12-4065-8dd1-fdb91da7eecf",
    "instance_uuid": "8b4b4a25-3b15-47ea-b701-db75d7da7346",
    "event_fields": [],
    "references": "https://abcdef.fr",
    "tags": [],
    "false_positives": None,
}


def test_create_alert(symphony_storage, nybble_module, arguments):

    arguments.rule = SEKOIA_ALERT_RULE_MOCK

    create_alert_action = CreateAlertAction(module=nybble_module, data_path=symphony_storage)
    with requests_mock.Mocker() as mock:
        mock.post(
            f"{nybble_module.configuration.nhub_url}/conn/sekoia", json={"ok": "created with success"}, status_code=200
        )
        results = create_alert_action.run(arguments)

        assert results["status"] == True


def test_create_alert_noFields_noTags(symphony_storage, nybble_module, arguments):

    arguments.rule = SEKOIA_ALERT_RULE_MOCK_EMPTY

    create_alert_action = CreateAlertAction(module=nybble_module, data_path=symphony_storage)
    with requests_mock.Mocker() as mock:
        mock.post(
            f"{nybble_module.configuration.nhub_url}/conn/sekoia", json={"ok": "created with success"}, status_code=200
        )
        results = create_alert_action.run(arguments)

        assert results["status"] == True


def test_create_alert_missing_field(symphony_storage, nybble_module, arguments):

    arguments.rule = SEKOIA_ALERT_RULE_MOCK_EXTRA_FIELD

    create_alert_action = CreateAlertAction(module=nybble_module, data_path=symphony_storage)
    with requests_mock.Mocker() as mock:
        mock.post(
            f"{nybble_module.configuration.nhub_url}/conn/sekoia", json={"ok": "created with success"}, status_code=200
        )
        results = create_alert_action.run(arguments)

        assert results["status"] == True


def test_create_alert_error(symphony_storage, nybble_module, arguments):

    arguments.rule = SEKOIA_ALERT_RULE_MOCK
    create_alert_action = CreateAlertAction(module=nybble_module, data_path=symphony_storage)
    with requests_mock.Mocker() as mock:
        mock.post(
            f"{nybble_module.configuration.nhub_url}/conn/sekoia", json={"error": "dummy error"}, status_code=500
        )
        results = create_alert_action.run(arguments)

        assert results["status"] == False
