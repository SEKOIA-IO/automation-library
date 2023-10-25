from pathlib import Path
import pytest
import requests_mock

from tranco_module.triggers import FetchTrancoListTrigger


@pytest.fixture
def trigger(symphony_storage, config_storage: Path):
    trigger = FetchTrancoListTrigger(data_path=symphony_storage)
    trigger.configuration = {"interval": 0, "chunk_size": 5}
    trigger._token = "token"
    config_storage.joinpath(FetchTrancoListTrigger.CALLBACK_URL_FILE_NAME).write_text("https://callback.url/")
    return trigger


@pytest.fixture(autouse=True)
def mock(trigger):
    with requests_mock.mock() as m:
        m.post(trigger.callback_url)
        m.post("https://logs.url/")
        yield m


def test_create_event_for_chunk(trigger, mock):
    trigger.create_event_for_chunk(["google.com", "facebook.com"], 0)
    assert mock.called
    caller_params = mock.request_history[0].json()
    assert "name" in caller_params and caller_params["name"] == "Tranco List Chunk 0-2"
    assert "event" in caller_params
    assert "directory" in caller_params


def test_get_top_domains(trigger, mock):
    with open("tests/data/top-1m.csv.zip", "rb") as mock_fp:
        mock.get(trigger.top_domains_url, content=mock_fp.read())
        result = trigger.get_top_domains()
        assert isinstance(result, list)
        assert len(result) > 10


def test_run(trigger, mock):
    with open("tests/data/top-1m.csv.zip", "rb") as mock_fp:
        mock.get(trigger.top_domains_url, content=mock_fp.read())
        trigger._run()
        # 1 download of the zip, and 3 send events because chunk size = 5 and the zip has 13 domains
        assert mock.call_count == 4
