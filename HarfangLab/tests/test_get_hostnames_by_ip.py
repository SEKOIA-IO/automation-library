# tests/test_get_hostnames_by_ip.py

# coding: utf-8

# natives

import pytest
import requests_mock
from pydantic import ValidationError

# internals
from harfanglab.get_hostnames_by_ip_action import GetHostnamesByIP

# third parties
from harfanglab.models import HostnameEntry, HostnamesResult


def test_get_hostnames_by_ip():
    instance_url = "https://test.hurukau.io"
    api_token = "11111111111111111111111111111111"

    action = GetHostnamesByIP()
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    target_ip = "192.168.1.1"

    with requests_mock.Mocker() as mock:
        mocked_response = [
            {
                "hostname": "test-host",
                "ipaddress": target_ip,
                "lastseen": "2023-07-04T12:00:00Z",
                "ostype": "Windows",
                "status": "active",
            },
            {
                "hostname": "test-host-2",
                "ipaddress": target_ip,
                "lastseen": "2023-07-05T12:00:00Z",
                "ostype": "Linux",
                "status": "inactive",
            },
        ]
        mock.get(
            f"{instance_url}/api/data/endpoint/Agent/",
            json=mocked_response,
            headers={"Authorization": f"Token {api_token}"},
        )

        # Test with get_only_last_seen = False
        res = action.run({"target_ip": target_ip, "get_only_last_seen": False})
        expected_result = HostnamesResult(
            hostnames=[
                HostnameEntry(
                    hostname="test-host",
                    ipaddress=target_ip,
                    lastseen="2023-07-04T12:00:00Z",
                    ostype="Windows",
                    status="active",
                ),
                HostnameEntry(
                    hostname="test-host-2",
                    ipaddress=target_ip,
                    lastseen="2023-07-05T12:00:00Z",
                    ostype="Linux",
                    status="inactive",
                ),
            ]
        ).dict()
        assert res == expected_result

        # Test with get_only_last_seen = True
        res = action.run({"target_ip": target_ip, "get_only_last_seen": True})
        expected_result = HostnamesResult(
            hostnames=[
                HostnameEntry(
                    hostname="test-host-2",
                    ipaddress=target_ip,
                    lastseen="2023-07-05T12:00:00Z",
                    ostype="Linux",
                    status="inactive",
                )
            ]
        ).dict()
        assert res == expected_result


@pytest.mark.parametrize("target_ip", ["", "   "])
def test_get_hostnames_by_ip_requires_target_ip(target_ip):
    instance_url = "https://test.hurukau.io"
    api_token = "11111111111111111111111111111111"

    action = GetHostnamesByIP()
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            action.run({"target_ip": target_ip, "get_only_last_seen": False})

    assert len(mock.request_history) == 0


def test_get_hostnames_by_ip_rejects_invalid_target_ip_shape():
    instance_url = "https://test.hurukau.io"
    api_token = "11111111111111111111111111111111"

    action = GetHostnamesByIP()
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    with requests_mock.Mocker() as mock:
        with pytest.raises(ValidationError):
            action.run({"target_ip": "not-an-ip", "get_only_last_seen": False})

    assert len(mock.request_history) == 0
