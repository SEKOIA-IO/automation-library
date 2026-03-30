from uuid import UUID

import pytest
import requests


from sekoiaio.operation_center.create_dataset import CreateDataset

BASE_URL = "https://fake.url/"
API_KEY = "fake_api_key"
DATASETS_URL = "https://fake.url/api/v1/notebooks/datasets"
VALIDATE_URL = "https://fake.url/api/v1/notebooks/datasets/validate"


def make_action() -> CreateDataset:
    action = CreateDataset()
    action.module.configuration = {"base_url": BASE_URL, "api_key": API_KEY}
    return action


# ---------------------------------------------------------------------------
# run() — happy path
# ---------------------------------------------------------------------------


def test_create_dataset_success(requests_mock):
    action = make_action()

    mock_created_response = {
    "uuid": "aaaaaaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "community_uuid": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
    "name": "mock_dataset",
    "size": 0.0,
    "created_by": "cccccccc-cccc-cccc-cccc-cccccccccccc",
    "created_by_type": "user",
    "created_at": "1970-01-01T00:00:00.000000Z",
    "fields": [
        {
            "name": "column1",
        },
        {
            "name": "column2",
        }
    ]
}
    requests_mock.post(VALIDATE_URL, status_code=200, json=mock_created_response)
    requests_mock.post(DATASETS_URL, status_code=201, json=mock_created_response)

    result = action.run(
        {
            "name": "my_dataset",
            "dataset": "column1,column2\nval1,val2",
        }
    )

    assert result is None or result == {}
    assert requests_mock.call_count == 2
    assert len(action._logs) == 0


# ---------------------------------------------------------------------------
# validate_dataset() — HTTP error
# ---------------------------------------------------------------------------


def test_validate_dataset_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()

    mock_validate_response = {
    "detail": {
        "message": "Row has 1 columns but expected 2 columns",
        "code": "DATASET_VALIDATION_ERROR"
    }
}

    requests_mock.post(VALIDATE_URL, status_code=422, json=mock_validate_response)

    with pytest.raises(requests.exceptions.HTTPError):
        action.validate_dataset(b"col1\nval1", "my_dataset")

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when validating dataset" in action._logs[0]["message"]
    assert "Response status: 422" in action._logs[0]["message"]
    assert "Row has 1 columns but expected 2 columns" in action._logs[0]["message"]


def test_validate_dataset_server_error(requests_mock):
    action = make_action()
    action.configure_http_session()

    requests_mock.post(VALIDATE_URL, status_code=500, text="Internal Server Error")

    with pytest.raises(requests.exceptions.HTTPError):
        action.validate_dataset(b"col1\nval1", "my_dataset")

    assert action._logs[0]["level"] == "error"
    assert "Response status: 500" in action._logs[0]["message"]


# ---------------------------------------------------------------------------
# create_dataset() — HTTP error
# ---------------------------------------------------------------------------


def test_create_dataset_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()



    mock_create_response = {
    "detail": {
        "message": "A dataset with this name already exists in the community",
        "code": "DATASET_VALIDATION_ERROR"
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


def test_run_stops_on_validate_error(requests_mock):
    """If validate fails, create should never be called."""
    action = make_action()

    requests_mock.post(VALIDATE_URL, status_code=422, text="Unprocessable entity")
    create_mock = requests_mock.post(DATASETS_URL, status_code=201)

    with pytest.raises(requests.exceptions.HTTPError):
        action.run({"name": "my_dataset", "dataset": "col1\nval1"})

    assert not create_mock.called


# ---------------------------------------------------------------------------
# encode_dataset()
# ---------------------------------------------------------------------------


def test_encode_dataset_returns_utf8_bytes(requests_mock):
    action = make_action()
    action.configure_http_session()

    dataset_str = "col1,col2\nval1,val2"
    result = action.encode_dataset(dataset_str)

    assert isinstance(result, bytes)
    assert result == dataset_str.encode("utf-8")


def test_encode_dataset_handles_unicode(requests_mock):
    action = make_action()
    action.configure_http_session()

    dataset_str = "name\néàü"
    result = action.encode_dataset(dataset_str)

    assert isinstance(result, bytes)
    assert result.decode("utf-8") == dataset_str
