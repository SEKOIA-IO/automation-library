# tests/test_get_hostnames_by_ip.py

# coding: utf-8

# natives
import requests_mock

# third parties
from harfanglab.models import HostnamesResult, HostnameEntry

# internals
from harfanglab.get_hostnames_by_ip_action import GetHostnamesByIP


def test_get_hostnames_by_ip():
    instance_url = "https://test.hurukau.io"
    api_token = "117a15380a4f434c94fbe1ea7052904e"

    action = GetHostnamesByIP()
    action.module.configuration = {"url": instance_url, "api_token": api_token}

    target_ip = "192.168.1.1"

    with requests_mock.Mocker() as mock:
        mocked_response = [
            {
                "hostname": "test-host",
                "ipaddress": target_ip,
                "last_seen": "2023-07-04T12:00:00Z",
                "os": "Windows",
                "status": "active",
            },
            {
                "hostname": "test-host-2",
                "ipaddress": target_ip,
                "last_seen": "2023-07-05T12:00:00Z",
                "os": "Linux",
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
                    last_seen="2023-07-04T12:00:00Z",
                    os="Windows",
                    status="active",
                ),
                HostnameEntry(
                    hostname="test-host-2",
                    ipaddress=target_ip,
                    last_seen="2023-07-05T12:00:00Z",
                    os="Linux",
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
                    last_seen="2023-07-05T12:00:00Z",
                    os="Linux",
                    status="inactive",
                )
            ]
        ).dict()
        assert res == expected_result
