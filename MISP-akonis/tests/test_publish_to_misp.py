import tempfile
import uuid
from pathlib import Path

import orjson
import pytest
from misp.publish_to_misp import PublishToMISPAction


@pytest.fixture
def misp_api(misp_base_server, misp_event, requests_mock, misp_base_url: str):
    requests_mock.post(misp_base_url + "events/add", json=misp_event)

    yield requests_mock


def test_misp_to_stix(misp_event, misp_api, misp_base_url: str):
    action = PublishToMISPAction()
    action.module.configuration = {
        "misp_url": misp_base_url,
        "misp_api_key": "fake_api_key",
    }

    result = action.run({"event": misp_event})
    assert isinstance(result, dict)
    assert "event" in result
    assert "Event" in result["event"]


def test_misp_to_stix_through_files(misp_event, misp_api, misp_base_url: str):
    with tempfile.TemporaryDirectory() as directory:
        data_path = Path(directory)
        action = PublishToMISPAction(data_path=data_path)
        action.module.configuration = {
            "misp_url": misp_base_url,
            "misp_api_key": "fake_api_key",
        }

        filename = f"{uuid.uuid4()}.json"
        with data_path.joinpath(filename).open("w") as f:
            f.write(orjson.dumps(misp_event).decode("utf-8"))

        result = action.run({"event_path": filename})
        assert isinstance(result, dict)
        assert "event_path" in result
