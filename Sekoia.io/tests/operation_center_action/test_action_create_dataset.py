from uuid import UUID, uuid4

import pytest
import requests


from sekoiaio.operation_center.create_dataset import CreateDataset

BASE_URL = "https://fake.url/"
API_KEY = "fake_api_key"
DATASETS_URL = "https://fake.url/api/v1/notebooks/datasets"
VALIDATE_URL = "https://fake.url/api/v1/notebooks/datasets/validate"

DATASET_UUID = str(uuid4())
COMMUNITY_UUID = str(uuid4())
CREATED_BY_UUID = str(uuid4())


def make_action() -> CreateDataset:
    action = CreateDataset()
    action.module.configuration = {"base_url": BASE_URL, "api_key": API_KEY}
    return action


# ---------------------------------------------------------------------------
# run() — happy path
# ---------------------------------------------------------------------------


def test_create_dataset_success(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    mock_created_response = {
        "uuid": DATASET_UUID,
        "community_uuid": COMMUNITY_UUID,
        "name": "my_dataset",
        "size": 0.0,
        "created_by": CREATED_BY_UUID,
        "created_by_type": "user",
        "created_at": "1970-01-01T00:00:00.000000Z",
        "fields": [
            {
                "name": "column1",
            },
            {
                "name": "column2",
            },
        ],
    }
    requests_mock.post(DATASETS_URL, status_code=201, json=mock_created_response)

    result = action.run(
        {
            "name": "my_dataset",
            "dataset": "column1,column2\nval1,val2",
        }
    )

    assert result is None or result == {}
    assert requests_mock.call_count == 1
    assert len(action._logs) == 0


# ---------------------------------------------------------------------------
# create_dataset() — HTTP error
# ---------------------------------------------------------------------------


def test_create_dataset_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    mock_create_response = {
        "detail": {
            "message": "A dataset with this name already exists in the community",
            "code": "DATASET_VALIDATION_ERROR",
        }
    }

    requests_mock.post(DATASETS_URL, status_code=422, json=mock_create_response)

    with pytest.raises(requests.exceptions.HTTPError):
        action.create_dataset(b"col1\nval1", "my_dataset")

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when creating dataset" in action._logs[0]["message"]
    assert "Response status: 422" in action._logs[0]["message"]
    assert "A dataset with this name already exists" in action._logs[0]["message"]


# ---------------------------------------------------------------------------
# encode_dataset()
# ---------------------------------------------------------------------------


def test_encode_dataset_returns_utf8_bytes(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    dataset_str = "col1,col2\nval1,val2"
    result = action.encode_dataset(dataset_str)

    assert isinstance(result, bytes)
    assert result == dataset_str.encode("utf-8")


def test_encode_dataset_handles_unicode(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    dataset_str = "name\néàü"
    result = action.encode_dataset(dataset_str)

    assert isinstance(result, bytes)
    assert result.decode("utf-8") == dataset_str
