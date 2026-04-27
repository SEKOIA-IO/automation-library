from uuid import UUID, uuid4

import pytest
import requests

from sekoiaio.operation_center.delete_dataset import DeleteDataset, DeleteDatasetArguments, DeleteDatasetResults

BASE_URL = "https://fake.url/"
API_KEY = "fake_api_key"
DATASETS_URL = "https://fake.url/api/v1/notebooks/datasets"

DATASET_UUID = str(uuid4())
COMMUNITY_UUID = str(uuid4())
CREATED_BY_UUID = str(uuid4())

# NOTE: DeleteDataset.run() contains a bug: it calls `arguments.dataset` but
# the DeleteDatasetArguments model only defines `name`. This raises AttributeError
# at runtime. The tests below exercise the individual methods directly.


def make_action() -> DeleteDataset:
    action = DeleteDataset()
    action.module.configuration = {"base_url": BASE_URL, "api_key": API_KEY}
    return action


# ---------------------------------------------------------------------------
# get_dataset_uuid()
# ---------------------------------------------------------------------------


def test_get_dataset_uuid_success(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    mock_list_response = {
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

    requests_mock.get(
        DATASETS_URL,
        json={"items": [mock_list_response], "total": 1},
    )

    result = action.get_dataset_uuid("my_dataset")

    assert result == UUID(DATASET_UUID)
    assert requests_mock.last_request.qs["name"] == ["my_dataset"]


def test_get_dataset_uuid_not_found(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(
        DATASETS_URL,
        json={"items": [], "total": 0},
    )

    with pytest.raises(ValueError):
        action.get_dataset_uuid("missing_dataset")

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "No dataset found" in action._logs[0]["message"]
    assert "missing_dataset" in action._logs[0]["message"]


def test_get_dataset_uuid_multiple_found(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    mock_list_response_1 = {
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
    mock_list_response_2 = {
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

    requests_mock.get(
        DATASETS_URL,
        json={
            "items": [
                mock_list_response_1,
                mock_list_response_2,
            ],
            "total": 2,
        },
    )

    with pytest.raises(ValueError):
        action.get_dataset_uuid("my_dataset")

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "Multiple datasets found" in action._logs[0]["message"]


def test_get_dataset_uuid_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.get(DATASETS_URL, status_code=500, text="Internal Server Error")

    with pytest.raises(requests.exceptions.HTTPError):
        action.get_dataset_uuid("my_dataset")

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when retrieving existing datasets" in action._logs[0]["message"]
    assert "Response status: 500" in action._logs[0]["message"]
    assert "Internal Server Error" in action._logs[0]["message"]


# ---------------------------------------------------------------------------
# delete_dataset()
# ---------------------------------------------------------------------------


def test_delete_dataset_success(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.delete(f"{DATASETS_URL}/{DATASET_UUID}", status_code=204)

    result = action.delete_dataset(DATASET_UUID)

    assert len(action._logs) == 0
    assert result is None


def test_delete_dataset_by_uuid_success(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.delete(f"{DATASETS_URL}/{DATASET_UUID}", status_code=204)
    action.run(DeleteDatasetArguments(uuid=UUID(DATASET_UUID)))
    assert len(action._logs) == 0


def test_delete_dataset_http_error(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()

    requests_mock.delete(
        f"{DATASETS_URL}/{DATASET_UUID}",
        status_code=403,
        text="Forbidden: insufficient permissions",
    )

    with pytest.raises(requests.exceptions.HTTPError):
        action.delete_dataset(DATASET_UUID)

    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when deleting dataset" in action._logs[0]["message"]
    assert "Response status: 403" in action._logs[0]["message"]
    assert "Forbidden: insufficient permissions" in action._logs[0]["message"]


def test_delete_dataset_not_found(requests_mock):
    action = make_action()
    action.configure_http_session()
    action.configure_urls()
    mock_not_found_response = {"detail": {"message": "Dataset does not exist", "code": "DATASET_NOT_FOUND"}}

    requests_mock.delete(
        f"{DATASETS_URL}/{DATASET_UUID}",
        status_code=404,
        json=mock_not_found_response,
    )

    with pytest.raises(requests.exceptions.HTTPError):
        action.delete_dataset(DATASET_UUID)

    assert action._logs[0]["level"] == "error"
    assert "Response status: 404" in action._logs[0]["message"]
