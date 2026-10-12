import json
import uuid
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
import requests
import requests_mock
from sekoia_automation.constants import EVENT_BYTES_MAX_SIZE

from sekoiaio.operation_center.push_event_to_intake import PushEventToIntake

module_base_url = "https://app.sekoia.fake/"
base_url = module_base_url + "batch"
apikey = "fake_api_key"


@pytest.fixture(autouse=True, scope="session")
def symphony_storage():
    new_storage = Path(mkdtemp())

    yield new_storage

    rmtree(new_storage.as_posix())


def test_push_event_to_intake_with_one_event():
    action = PushEventToIntake()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    with requests_mock.Mocker() as mock:
        mock.post("https://intake.sekoia.fake/batch", json={"event_ids": ["001"]})

        results: dict = action.run(
            {
                "intake_server": "https://intake.sekoia.fake",
                "intake_key": "my_intake_key",
                "event": "my fake event",
            }
        )
        assert len(results["event_ids"]) == 1


def test_push_event_to_intake_with_multiple_event():
    action = PushEventToIntake()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    with requests_mock.Mocker() as mock:
        mock.post("https://intake.sekoia.fake/batch", json={"event_ids": ["001", "002"]})

        results: dict = action.run(
            {
                "intake_server": "https://intake.sekoia.fake",
                "intake_key": "my_intake_key",
                "events": ["my fake event", "another fake event"],
            }
        )
        assert len(results["event_ids"]) == 2


def test_push_event_to_intake_from_file(symphony_storage):
    action = PushEventToIntake()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    file_path = symphony_storage / str(uuid.uuid4())

    with file_path.open("w") as fd:
        json.dump("my fake event", fd)

    with requests_mock.Mocker() as mock:
        mock.post("https://intake.sekoia.fake/batch", json={"event_ids": ["001"]})

        results: dict = action.run(
            {
                "intake_server": "https://intake.sekoia.fake",
                "intake_key": "my_intake_key",
                "event_path": file_path,
                "keep_file_after_push": False,
            }
        )
        assert len(results["event_ids"]) == 1
        assert not file_path.exists()


def test_push_events_to_intake_from_file(symphony_storage):
    action = PushEventToIntake()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    file_path = symphony_storage / str(uuid.uuid4())

    with file_path.open("w") as fd:
        json.dump(["my fake event", "another fake event"], fd)

    with requests_mock.Mocker() as mock:
        mock.post("https://intake.sekoia.fake/batch", json={"event_ids": ["001", "002"]})

        results: dict = action.run(
            {
                "intake_server": "https://intake.sekoia.fake",
                "intake_key": "my_intake_key",
                "events_path": file_path,
            }
        )
        assert len(results["event_ids"]) == 2
        assert not file_path.exists()


def test_push_events_to_intake_from_file_should_keep_file_after_push(symphony_storage):
    action = PushEventToIntake()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    file_path = symphony_storage / str(uuid.uuid4())

    with file_path.open("w") as fd:
        json.dump(["my fake event", "another fake event"], fd)

    with requests_mock.Mocker() as mock:
        mock.post("https://intake.sekoia.fake/batch", json={"event_ids": ["001", "002"]})

        results: dict = action.run(
            {
                "intake_server": "https://intake.sekoia.fake",
                "intake_key": "my_intake_key",
                "events_path": file_path,
                "keep_file_after_push": True,
            }
        )
        assert len(results["event_ids"]) == 2
        assert file_path.exists()


def test_push_event_to_intake_with_retries():
    action = PushEventToIntake()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    with requests_mock.Mocker() as mock:
        mock.post(
            "https://intake.sekoia.fake/batch",
            [
                {"exc": requests.exceptions.ConnectTimeout},
                {"status_code": 500},
                {"json": {"event_ids": ["001"]}},
            ],
        )

        results: dict = action.run(
            {
                "intake_server": "https://intake.sekoia.fake",
                "intake_key": "my_intake_key",
                "event": "my fake event",
            }
        )
        assert len(results["event_ids"]) == 1


def test_push_event_to_intake_should_not_retry():
    action = PushEventToIntake()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    with requests_mock.Mocker() as mock:
        mock.post(
            "https://intake.sekoia.fake/batch",
            [
                {"status_code": 400},
                {"json": {"event_ids": ["001"]}},
            ],
        )

        results: dict = action.run(
            {
                "intake_server": "https://intake.sekoia.fake",
                "intake_key": "my_intake_key",
                "event": "my fake event",
            }
        )
        assert len(results["event_ids"]) == 0


def test_push_event_to_intake_serializes_non_string_events():
    action = PushEventToIntake()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    with requests_mock.Mocker() as mock:
        mock.post("https://intake.sekoia.fake/batch", json={"event_ids": ["001", "002", "003"]})

        results: dict = action.run(
            {
                "intake_server": "https://intake.sekoia.fake",
                "intake_key": "my_intake_key",
                "event": {"message": "single"},
                "events": [{"message": "first"}, "raw event"],
            }
        )

        assert results["event_ids"] == ["001", "002", "003"]
        assert mock.last_request.json() == {
            "intake_key": "my_intake_key",
            "jsons": ['{"message": "single"}', '{"message": "first"}', "raw event"],
        }


def test_push_event_to_intake_without_event():
    action = PushEventToIntake()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    with requests_mock.Mocker() as mock:
        results: dict = action.run({"intake_server": "https://intake.sekoia.fake", "intake_key": "my_intake_key"})

        assert results == {"event_ids": []}
        assert mock.call_count == 0

    assert action._logs[-1]["message"] == "No event to push"


def test_push_event_to_intake_discards_too_long_events():
    action = PushEventToIntake()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    too_long_event = "a" * (EVENT_BYTES_MAX_SIZE + 1)

    with requests_mock.Mocker() as mock:
        mock.post("https://intake.sekoia.fake/batch", json={"event_ids": ["001"]})

        results: dict = action.run(
            {
                "intake_server": "https://intake.sekoia.fake",
                "intake_key": "my_intake_key",
                "events": [too_long_event, "my fake event"],
            }
        )

        assert results["event_ids"] == ["001"]
        assert mock.call_count == 1
        assert mock.last_request.json()["jsons"] == ["my fake event"]

    assert any(log["message"] == "1 too long events were discarded (length > 250kb)" for log in action._logs)


def test_push_event_to_intake_splits_events_in_chunks(monkeypatch):
    # each chunk can hold two 10-byte events
    monkeypatch.setattr("sekoiaio.operation_center.push_event_to_intake.CHUNK_BYTES_MAX_SIZE", 25)
    action = PushEventToIntake(max_workers=1)
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    events = [f"event-{index:04d}" for index in range(5)]

    with requests_mock.Mocker() as mock:
        mock.post(
            "https://intake.sekoia.fake/batch",
            [
                {"json": {"event_ids": ["001", "002"]}},
                {"json": {"event_ids": ["003", "004"]}},
                {"json": {"event_ids": ["005"]}},
            ],
        )

        results: dict = action.run(
            {"intake_server": "https://intake.sekoia.fake", "intake_key": "my_intake_key", "events": events}
        )

        assert [request.json()["jsons"] for request in mock.request_history] == [
            events[0:2],
            events[2:4],
            events[4:5],
        ]
        assert results["event_ids"] == ["001", "002", "003", "004", "005"]
