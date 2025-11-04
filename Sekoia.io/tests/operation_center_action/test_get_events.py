from unittest.mock import patch, Mock

import pytest
import requests
import urllib3
from sekoiaio.operation_center.get_events import GetEvents

module_base_url = "https://fake.url/"
base_url = module_base_url + "api/v1/sic/"
apikey = "fake_api_key"


def test_get_events(requests_mock):
    action = GetEvents()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {
        "query": 'source.ip:"127.0.0.1" OR destination.ip:"127.0.0.1"',
        "earliest_time": "-1d",
        "latest_time": "now",
        "fields": "event.dialect,action.outcome,action.id",
        "limit": 6,
    }

    requests_mock.post(
        "https://fake.url/api/v1/sic/conf/events/search/jobs",
        json={"uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"},
    )

    requests_mock.get(
        "https://fake.url/api/v1/sic/conf/events/search/jobs/483d36a5-8538-49c4-be19-49b669f90bf8",
        json={
            "canceled_by_type": None,
            "view_uuid": None,
            "term": arguments["query"],
            "expired": False,
            "earliest_time": arguments["earliest_time"],
            "results_ttl": 600,
            "created_by": "99671aa8-857f-49be-85b4-bcf1bc4df398",
            "started_at": "2021-05-26T09:19:58.469271+00:00",
            "total": 3,
            "canceled_by": None,
            "created_at": "2021-05-26T09:19:57.469271+00:00",
            "created_by_type": "avatar",
            "canceled_at": None,
            "ended_at": "2021-05-26T09:19:59.469271+00:00",
            "latest_time": arguments["latest_time"],
            "status": 2,
            "uuid": "483d36a5-8538-49c4-be19-49b669f90bf8",
            "term_lang": "dork",
        },
    )
    events = [
        {
            "name": "action.id",
            "value_type": "number",
            "description": "Identifier of the action",
            "display_name": "action.id",
            "most_common_values": [],
        },
        {
            "display_name": "event.dialect",
            "description": "Dialect of the event",
            "most_common_values": [{"value": 100.0, "name": "openssh"}],
            "value_type": "string",
            "name": "event.dialect",
        },
        {
            "name": "action.outcome",
            "value_type": "string",
            "description": "Result of the action",
            "display_name": "action.outcome",
            "most_common_values": [
                {"value": 50.0, "name": "False"},
                {"value": 50.0, "name": "True"},
            ],
        },
        {
            "name": "action.outcome_reason",
            "value_type": "string",
            "description": "The reason of the failure/success",
            "display_name": "action.outcome_reason",
        },
        {
            "name": "action.properties.AccessList",
            "value_type": "string",
            "description": "",
            "display_name": "action.properties.AccessList",
            "most_common_values": [
                {"value": 50.0, "name": "val1"},
                {"value": 50.0, "name": "val2"},
            ],
        },
        {
            "name": "action.properties.AccessMask",
            "value_type": "string",
            "description": "",
            "display_name": "action.properties.AccessMask",
        },
    ]
    requests_mock.get(
        (
            "https://fake.url/api/v1/sic/conf/events/search/jobs/"
            "483d36a5-8538-49c4-be19-49b669f90bf8/events?limit=6&offset=0"
        ),
        json={
            "items": events,
            "total": 6,
        },
    )

    results: dict = action.run(arguments)
    assert results["events"] == events


def test_not_events_found(requests_mock):
    action = GetEvents()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {
        "query": 'source.ip:"127.0.0.1" OR destination.ip:"127.0.0.1"',
        "earliest_time": "-1d",
        "latest_time": "now",
        "fields": "event.dialect,action.outcome,action.id",
    }

    requests_mock.post(
        "https://fake.url/api/v1/sic/conf/events/search/jobs",
        json={"uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"},
    )

    requests_mock.get(
        "https://fake.url/api/v1/sic/conf/events/search/jobs/483d36a5-8538-49c4-be19-49b669f90bf8",
        json={"status": 2, "uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"},
    )

    requests_mock.get(
        (
            "https://fake.url/api/v1/sic/conf/events/search/jobs/"
            "483d36a5-8538-49c4-be19-49b669f90bf8/events?limit=100&offset=0"
        ),
        json={
            "items": [],
            "total": 0,
        },
    )

    results: dict = action.run(arguments)
    assert results["events"] == []


def test_not_events_found_but_total(requests_mock):
    action = GetEvents()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {
        "query": 'source.ip:"127.0.0.1" OR destination.ip:"127.0.0.1"',
        "earliest_time": "-1d",
        "latest_time": "now",
        "fields": "event.dialect,action.outcome,action.id",
    }

    requests_mock.post(
        "https://fake.url/api/v1/sic/conf/events/search/jobs",
        json={"uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"},
    )

    requests_mock.get(
        "https://fake.url/api/v1/sic/conf/events/search/jobs/483d36a5-8538-49c4-be19-49b669f90bf8",
        json={"status": 2, "uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"},
    )

    requests_mock.get(
        (
            "https://fake.url/api/v1/sic/conf/events/search/jobs/"
            "483d36a5-8538-49c4-be19-49b669f90bf8/events?limit=100&offset=0"
        ),
        json={
            "items": [],
            "total": 100,
        },
    )

    results: dict = action.run(arguments)
    assert results["events"] == []
    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"


def test_get_events_with_retries(requests_mock):
    action = GetEvents()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {
        "query": 'source.ip:"127.0.0.1" OR destination.ip:"127.0.0.1"',
        "earliest_time": "-1d",
        "latest_time": "now",
        "fields": "event.dialect,action.outcome,action.id",
        "limit": 6,
    }

    requests_mock.post(
        "https://fake.url/api/v1/sic/conf/events/search/jobs",
        json={"uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"},
    )

    status_mock = requests_mock.get(
        "https://fake.url/api/v1/sic/conf/events/search/jobs/483d36a5-8538-49c4-be19-49b669f90bf8",
        [
            # The job is pending
            {
                "json": {
                    "canceled_by_type": None,
                    "view_uuid": None,
                    "term": arguments["query"],
                    "expired": False,
                    "earliest_time": arguments["earliest_time"],
                    "results_ttl": 600,
                    "created_by": "99671aa8-857f-49be-85b4-bcf1bc4df398",
                    "started_at": None,
                    "total": 0,
                    "canceled_by": None,
                    "created_at": "2021-05-26T09:19:57.469271+00:00",
                    "created_by_type": "avatar",
                    "canceled_at": None,
                    "ended_at": None,
                    "latest_time": arguments["latest_time"],
                    "status": 0,
                    "uuid": "483d36a5-8538-49c4-be19-49b669f90bf8",
                    "term_lang": "dork",
                },
                "status_code": 200,
            },
            # The job is running
            {
                "json": {
                    "canceled_by_type": None,
                    "view_uuid": None,
                    "term": arguments["query"],
                    "expired": False,
                    "earliest_time": arguments["earliest_time"],
                    "results_ttl": 600,
                    "created_by": "99671aa8-857f-49be-85b4-bcf1bc4df398",
                    "started_at": "2021-05-26T09:19:58.469271+00:00",
                    "total": 3,
                    "canceled_by": None,
                    "created_at": "2021-05-26T09:19:57.469271+00:00",
                    "created_by_type": "avatar",
                    "canceled_at": None,
                    "ended_at": None,
                    "latest_time": arguments["latest_time"],
                    "status": 1,
                    "uuid": "483d36a5-8538-49c4-be19-49b669f90bf8",
                    "term_lang": "dork",
                },
                "status_code": 200,
            },
            # The job is done
            {
                "json": {
                    "canceled_by_type": None,
                    "view_uuid": None,
                    "term": arguments["query"],
                    "expired": False,
                    "earliest_time": arguments["earliest_time"],
                    "results_ttl": 600,
                    "created_by": "99671aa8-857f-49be-85b4-bcf1bc4df398",
                    "started_at": "2021-05-26T09:19:58.469271+00:00",
                    "total": 3,
                    "canceled_by": None,
                    "created_at": "2021-05-26T09:19:57.469271+00:00",
                    "created_by_type": "avatar",
                    "canceled_at": None,
                    "ended_at": "2021-05-26T09:19:59.469271+00:00",
                    "latest_time": arguments["latest_time"],
                    "status": 2,
                    "uuid": "483d36a5-8538-49c4-be19-49b669f90bf8",
                    "term_lang": "dork",
                },
                "status_code": 200,
            },
        ],
    )

    events = [
        {
            "name": "action.id",
            "value_type": "number",
            "description": "Identifier of the action",
            "display_name": "action.id",
            "most_common_values": [],
        },
        {
            "display_name": "event.dialect",
            "description": "Dialect of the event",
            "most_common_values": [{"value": 100.0, "name": "openssh"}],
            "value_type": "string",
            "name": "event.dialect",
        },
        {
            "name": "action.outcome",
            "value_type": "string",
            "description": "Result of the action",
            "display_name": "action.outcome",
            "most_common_values": [
                {"value": 50.0, "name": "False"},
                {"value": 50.0, "name": "True"},
            ],
        },
        {
            "name": "action.outcome_reason",
            "value_type": "string",
            "description": "The reason of the failure/success",
            "display_name": "action.outcome_reason",
        },
        {
            "name": "action.properties.AccessList",
            "value_type": "string",
            "description": "",
            "display_name": "action.properties.AccessList",
            "most_common_values": [
                {"value": 50.0, "name": "val1"},
                {"value": 50.0, "name": "val2"},
            ],
        },
        {
            "name": "action.properties.AccessMask",
            "value_type": "string",
            "description": "",
            "display_name": "action.properties.AccessMask",
        },
    ]
    requests_mock.get(
        (
            "https://fake.url/api/v1/sic/conf/events/search/jobs/"
            "483d36a5-8538-49c4-be19-49b669f90bf8/events?limit=6&offset=0"
        ),
        json={
            "items": events,
            "total": 6,
        },
    )

    results: dict = action.run(arguments)
    assert results["events"] == events
    assert status_mock.call_count == 3


def test_trigger_event_search_job_http_error(requests_mock):
    """Test that HTTP errors during job triggering are properly logged"""
    action = GetEvents()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {
        "query": 'source.ip:"127.0.0.1"',
        "earliest_time": "-1d",
        "latest_time": "now",
    }

    # Mock a 400 Bad Request response
    requests_mock.post(
        "https://fake.url/api/v1/sic/conf/events/search/jobs",
        status_code=400,
        text="Bad Request: Invalid query format",
    )

    with pytest.raises(requests.exceptions.HTTPError):
        action.run(arguments)

    # Check that an error was logged
    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert "HTTP error when triggering event search job" in action._logs[0]["message"]
    assert "Response status: 400" in action._logs[0]["message"]
    assert "Bad Request: Invalid query format" in action._logs[0]["message"]


def test_wait_for_search_job_initial_status_error(requests_mock):
    """Test that HTTP errors during initial status check are properly logged"""
    action = GetEvents()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {
        "query": 'source.ip:"127.0.0.1"',
        "earliest_time": "-1d",
        "latest_time": "now",
    }

    # Mock successful job creation
    requests_mock.post(
        "https://fake.url/api/v1/sic/conf/events/search/jobs",
        json={"uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"},
    )

    # Mock 500 error on initial status check
    requests_mock.get(
        "https://fake.url/api/v1/sic/conf/events/search/jobs/483d36a5-8538-49c4-be19-49b669f90bf8",
        status_code=500,
        text="Internal Server Error",
    )

    with pytest.raises(requests.exceptions.HTTPError):
        action.run(arguments)

    # Check that an error was logged
    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert (
        "HTTP error during initial status check for job 483d36a5-8538-49c4-be19-49b669f90bf8"
        in action._logs[0]["message"]
    )
    assert "Response status: 500" in action._logs[0]["message"]
    assert "Internal Server Error" in action._logs[0]["message"]


def test_wait_for_search_job_polling_error(requests_mock):
    """Test that HTTP errors during job status polling are properly logged"""
    action = GetEvents()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {
        "query": 'source.ip:"127.0.0.1"',
        "earliest_time": "-1d",
        "latest_time": "now",
    }

    # Mock successful job creation
    requests_mock.post(
        "https://fake.url/api/v1/sic/conf/events/search/jobs",
        json={"uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"},
    )

    # Mock multiple status checks - first one succeeds, second one fails
    status_mock = requests_mock.get(
        "https://fake.url/api/v1/sic/conf/events/search/jobs/483d36a5-8538-49c4-be19-49b669f90bf8",
        [
            # Initial status check (job not started yet)
            {"json": {"status": 0, "uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"}, "status_code": 200},
            # Polling fails with 502 error
            {"text": "Bad Gateway", "status_code": 502},
        ],
    )

    with pytest.raises(requests.exceptions.HTTPError):
        action.run(arguments)

    # Check that an error was logged
    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert (
        "HTTP error during job status polling for job 483d36a5-8538-49c4-be19-49b669f90bf8"
        in action._logs[0]["message"]
    )
    assert "Response status: 502" in action._logs[0]["message"]
    assert "Bad Gateway" in action._logs[0]["message"]


def test_get_events_http_error(requests_mock):
    """Test that HTTP errors during event retrieval are properly logged"""
    action = GetEvents()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {
        "query": 'source.ip:"127.0.0.1"',
        "earliest_time": "-1d",
        "latest_time": "now",
    }

    # Mock successful job creation
    requests_mock.post(
        "https://fake.url/api/v1/sic/conf/events/search/jobs",
        json={"uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"},
    )

    # Mock successful job completion
    requests_mock.get(
        "https://fake.url/api/v1/sic/conf/events/search/jobs/483d36a5-8538-49c4-be19-49b669f90bf8",
        json={"status": 2, "uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"},
    )

    # Mock 403 error on event retrieval
    requests_mock.get(
        "https://fake.url/api/v1/sic/conf/events/search/jobs/483d36a5-8538-49c4-be19-49b669f90bf8/events?limit=100&offset=0",
        status_code=403,
        text="Forbidden: Insufficient permissions",
    )

    with pytest.raises(requests.exceptions.HTTPError):
        action.run(arguments)

    # Check that an error was logged
    assert len(action._logs) == 1
    assert action._logs[0]["level"] == "error"
    assert (
        "HTTP error when retrieving events for job 483d36a5-8538-49c4-be19-49b669f90bf8" in action._logs[0]["message"]
    )
    assert "Response status: 403" in action._logs[0]["message"]
    assert "Forbidden: Insufficient permissions" in action._logs[0]["message"]


def test_trigger_job_with_retries_on_connection_timeout(requests_mock):
    """
    Test that connection timeouts during job creation
    """
    action = GetEvents()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {
        "query": 'source.ip:"127.0.0.1" OR destination.ip:"127.0.0.1"',
        "earliest_time": "-1d",
        "latest_time": "now",
        "fields": "event.dialect,action.outcome,action.id",
        "limit": 6,
    }

    requests_mock.post(
        "https://fake.url/api/v1/sic/conf/events/search/jobs",
        [
            {"exc": requests.exceptions.ConnectTimeout},
            {
                "exc": urllib3.exceptions.ReadTimeoutError(
                    Mock(spec=urllib3.connectionpool.ConnectionPool), "test.sekoia.io", "Read timed out."
                )
            },
            {"json": {"uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"}, "status_code": 200},
        ],
    )

    requests_mock.get(
        "https://fake.url/api/v1/sic/conf/events/search/jobs/483d36a5-8538-49c4-be19-49b669f90bf8",
        json={
            "canceled_by_type": None,
            "view_uuid": None,
            "term": arguments["query"],
            "expired": False,
            "earliest_time": arguments["earliest_time"],
            "results_ttl": 600,
            "created_by": "99671aa8-857f-49be-85b4-bcf1bc4df398",
            "started_at": "2021-05-26T09:19:58.469271+00:00",
            "total": 3,
            "canceled_by": None,
            "created_at": "2021-05-26T09:19:57.469271+00:00",
            "created_by_type": "avatar",
            "canceled_at": None,
            "ended_at": "2021-05-26T09:19:59.469271+00:00",
            "latest_time": arguments["latest_time"],
            "status": 2,
            "uuid": "483d36a5-8538-49c4-be19-49b669f90bf8",
            "term_lang": "dork",
        },
    )
    events = [
        {
            "name": "action.id",
            "value_type": "number",
            "description": "Identifier of the action",
            "display_name": "action.id",
            "most_common_values": [],
        },
    ]
    requests_mock.get(
        (
            "https://fake.url/api/v1/sic/conf/events/search/jobs/"
            "483d36a5-8538-49c4-be19-49b669f90bf8/events?limit=6&offset=0"
        ),
        json={
            "items": events,
            "total": 6,
        },
    )

    with patch("tenacity.nap.time"):
        results: dict = action.run(arguments)
        assert results["events"] == events


def test_wait_for_job_with_retries_on_connection_timeout(requests_mock):
    """
    Test that connection timeouts when waiting for job completion
    """
    action = GetEvents()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {
        "query": 'source.ip:"127.0.0.1" OR destination.ip:"127.0.0.1"',
        "earliest_time": "-1d",
        "latest_time": "now",
        "fields": "event.dialect,action.outcome,action.id",
        "limit": 6,
    }

    requests_mock.post(
        "https://fake.url/api/v1/sic/conf/events/search/jobs", json={"uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"}
    )

    requests_mock.get(
        "https://fake.url/api/v1/sic/conf/events/search/jobs/483d36a5-8538-49c4-be19-49b669f90bf8",
        [
            {"exc": requests.exceptions.ConnectTimeout},
            {
                "exc": urllib3.exceptions.ReadTimeoutError(
                    Mock(spec=urllib3.connectionpool.ConnectionPool), "test.sekoia.io", "Read timed out."
                )
            },
            {
                "json": {
                    "canceled_by_type": None,
                    "view_uuid": None,
                    "term": arguments["query"],
                    "expired": False,
                    "earliest_time": arguments["earliest_time"],
                    "results_ttl": 600,
                    "created_by": "99671aa8-857f-49be-85b4-bcf1bc4df398",
                    "started_at": "2021-05-26T09:19:58.469271+00:00",
                    "total": 3,
                    "canceled_by": None,
                    "created_at": "2021-05-26T09:19:57.469271+00:00",
                    "created_by_type": "avatar",
                    "canceled_at": None,
                    "ended_at": "2021-05-26T09:19:59.469271+00:00",
                    "latest_time": arguments["latest_time"],
                    "status": 2,
                    "uuid": "483d36a5-8538-49c4-be19-49b669f90bf8",
                    "term_lang": "dork",
                }
            },
        ],
    )
    events = [
        {
            "name": "action.id",
            "value_type": "number",
            "description": "Identifier of the action",
            "display_name": "action.id",
            "most_common_values": [],
        },
    ]
    requests_mock.get(
        (
            "https://fake.url/api/v1/sic/conf/events/search/jobs/"
            "483d36a5-8538-49c4-be19-49b669f90bf8/events?limit=6&offset=0"
        ),
        json={
            "items": events,
            "total": 6,
        },
    )

    with patch("tenacity.nap.time"):
        results: dict = action.run(arguments)
        assert results["events"] == events


def test_get_job_result_with_retries_on_connection_timeout(requests_mock):
    """
    Test that connection timeouts during job result retrieval
    """
    action = GetEvents()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    arguments = {
        "query": 'source.ip:"127.0.0.1" OR destination.ip:"127.0.0.1"',
        "earliest_time": "-1d",
        "latest_time": "now",
        "fields": "event.dialect,action.outcome,action.id",
        "limit": 6,
    }

    requests_mock.post(
        "https://fake.url/api/v1/sic/conf/events/search/jobs", json={"uuid": "483d36a5-8538-49c4-be19-49b669f90bf8"}
    )

    requests_mock.get(
        "https://fake.url/api/v1/sic/conf/events/search/jobs/483d36a5-8538-49c4-be19-49b669f90bf8",
        json={
            "canceled_by_type": None,
            "view_uuid": None,
            "term": arguments["query"],
            "expired": False,
            "earliest_time": arguments["earliest_time"],
            "results_ttl": 600,
            "created_by": "99671aa8-857f-49be-85b4-bcf1bc4df398",
            "started_at": "2021-05-26T09:19:58.469271+00:00",
            "total": 3,
            "canceled_by": None,
            "created_at": "2021-05-26T09:19:57.469271+00:00",
            "created_by_type": "avatar",
            "canceled_at": None,
            "ended_at": "2021-05-26T09:19:59.469271+00:00",
            "latest_time": arguments["latest_time"],
            "status": 2,
            "uuid": "483d36a5-8538-49c4-be19-49b669f90bf8",
            "term_lang": "dork",
        },
    )
    events = [
        {
            "name": "action.id",
            "value_type": "number",
            "description": "Identifier of the action",
            "display_name": "action.id",
            "most_common_values": [],
        },
    ]
    requests_mock.get(
        (
            "https://fake.url/api/v1/sic/conf/events/search/jobs/"
            "483d36a5-8538-49c4-be19-49b669f90bf8/events?limit=6&offset=0"
        ),
        [
            {"exc": requests.exceptions.ConnectTimeout},
            {
                "exc": urllib3.exceptions.ReadTimeoutError(
                    Mock(spec=urllib3.connectionpool.ConnectionPool), "test.sekoia.io", "Read timed out."
                )
            },
            {
                "json": {
                    "items": events,
                    "total": 6,
                }
            },
        ],
    )

    with patch("tenacity.nap.time"):
        results: dict = action.run(arguments)
        assert results["events"] == events
