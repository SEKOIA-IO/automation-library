import pytest
import requests

from sophos_module.actions.action_sophos_edr_run_scan import ActionSophosEDRScan
from tests.actions.conftest import DATA_REGION, ENDPOINT_ID

SCAN_URL = f"{DATA_REGION}/endpoint/v1/endpoints/{ENDPOINT_ID}/scans"


def test_run_scan(module, mock_api):
    scan = {"id": "41d45256-d5e0-4f56-bfb4-57c5de6909d9", "status": "requested"}
    mock_api.post(SCAN_URL, json=scan)

    assert ActionSophosEDRScan(module).run({"endpoint_id": ENDPOINT_ID}) == scan
    assert mock_api.last_request.json() == {}


@pytest.mark.parametrize("status_code", [400, 404])
def test_run_scan_error(module, mock_api, status_code):
    mock_api.post(SCAN_URL, status_code=status_code, json={"error": "notFound", "message": "Unknown endpoint"})

    with pytest.raises(requests.HTTPError):
        ActionSophosEDRScan(module).run({"endpoint_id": ENDPOINT_ID})
