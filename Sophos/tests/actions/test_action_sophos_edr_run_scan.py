import requests_mock

from sophos_module.actions.action_sophos_edr_run_scan import ActionSophosEDRScan


def test_run_scan(module, add_auth_mock) -> None:
    with requests_mock.Mocker() as mock:
        host = "https://api-eu01.central.sophos.com"
        add_auth_mock(mock, host, module)

        url = f"{host}/endpoint/v1/endpoints/0b44b37f-2299-47c8-bf5d-589995f8de96/scans"
        mock.post(
            url,
            json={
                "id": "41d45256-d5e0-4f56-bfb4-57c5de6909d9",
                "status": "requested",
                "requestedAt": "2024-10-03T10:29:58.170278201Z",
            },
        )
        scan_action = ActionSophosEDRScan(module, add_auth_mock)
        scan_action.run({"endpoint_id": "0b44b37f-2299-47c8-bf5d-589995f8de96"})
