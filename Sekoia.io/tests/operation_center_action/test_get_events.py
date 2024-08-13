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
