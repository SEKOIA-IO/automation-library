import json
import uuid
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

import pytest
import requests_mock

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
