from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, call, patch

import orjson
import pytest
from azure.mgmt.securityinsight.models import Incident, IncidentAdditionalData, IncidentLabel, IncidentOwnerInfo

from microsoft_sentinel import MicrosoftSentinelModule
from microsoft_sentinel.connector_microsoft_sentinel import MicrosoftSentineldConnector


@pytest.fixture
def trigger(symphony_storage):
    module = MicrosoftSentinelModule()
    trigger = MicrosoftSentineldConnector(module=module, data_path=symphony_storage)
    trigger.module.configuration = {
        "tenant_id": "123456",
        "client_id": "my-id",
        "client_secret": "my-password",
        "subscription_id": "4feff6df-7454-4036-923d-7b2444462416",
        "resource_group": "resource_group",
        "workspace_name": "workspace_name",
    }

    trigger.configuration = {
        "frequency": 60,
        "chunk_size": 2,
        "intake_server": "https://intake.sekoia.io",
        "intake_key": "0123456789",
    }

    trigger.push_events_to_intakes = Mock()
    trigger.log_exception = Mock()
    trigger.log = Mock()

    return trigger


@pytest.fixture
def additional_data_object():
    add_data = IncidentAdditionalData()
    add_data.additional_properties = {}
    add_data.alerts_count = 3
    add_data.bookmarks_count = 2
    add_data.comments_count = 1
    add_data.alert_product_names = ["alert_product_names"]
    add_data.tactics = ["tactics"]
    return add_data


@pytest.fixture
def incident_owner_object():
    owner_data = IncidentOwnerInfo()
    owner_data.additional_properties = {}
    owner_data.assigned_to = "Joe Done"
    owner_data.email = "joe.done@gmail.com"
    owner_data.user_principal_name = "Joe Done"
    owner_data.object_id = "123456"
    return owner_data


@pytest.fixture
def incident_labels_object():
    labels_data = IncidentLabel(label_name="label_name", label_type="label_type")
    labels_data.additional_properties = {}
    return labels_data


@pytest.fixture
def first_incident_item(incident_labels_object, incident_owner_object, additional_data_object):
    incident = Incident()
    incident.additional_properties = {}
    incident.id = "/subscriptions/f00000000-0000-0000-0000-000000000000/resourceGroups/resource_group/providers/Microsoft.SecurityInsights/Incidents/"
    incident.name = "7f744677-21e3-42c9"
    incident.type = "Microsoft.SecurityInsights/Incidents"
    incident.system_data = None
    incident.etag = "00000000-0000-0000-0000-000000000000"
    incident.additional_data = additional_data_object
    incident.classification = None
    incident.classification_comment = None
    incident.classification_reason = None
    incident.created_time_utc = datetime(2021, 9, 1, 0, 0, 0, 0, tzinfo=UTC)
    incident.description = "description"
    incident.first_activity_time_utc = datetime(2021, 9, 1, 0, 0, 1, 0, tzinfo=UTC)
    incident.incident_url = "https://incident_url"
    incident.incident_number = "incident_number"
    incident.labels = [incident_labels_object, incident_labels_object, incident_labels_object]
    incident.last_activity_time_utc = datetime(2021, 9, 1, 0, 0, 2, 0, tzinfo=UTC)
    incident.last_modified_time_utc = datetime(2021, 9, 1, 0, 0, 3, 0, tzinfo=UTC)
    incident.owner = incident_owner_object
    incident.related_alert_ids = ["related_alert_ids"]
    incident.severity = "severity"
    incident.status = "status"
    incident.title = "title"
    return incident


@pytest.fixture
def second_incident_item(incident_labels_object, incident_owner_object, additional_data_object):
    incident = Incident()
    incident.additional_properties = {}
    incident.id = "/subscriptions/f00000000-0000-0000-0000-000000000000/resourceGroups/resource_group/providers/Microsoft.SecurityInsights/Incidents/"
    incident.name = "8a855788-32f4-53da"
    incident.type = "Microsoft.SecurityInsights/Incidents"
    incident.system_data = None
    incident.etag = "00000000-0000-0000-0000-000000000000"
    incident.additional_data = additional_data_object
    incident.classification = None
    incident.classification_comment = None
    incident.classification_reason = None
    incident.created_time_utc = datetime(2021, 9, 1, 0, 0, 0, 0, tzinfo=UTC)
    incident.description = "description 2"
    incident.first_activity_time_utc = datetime(2021, 9, 1, 0, 0, 1, 0, tzinfo=UTC)
    incident.incident_url = "https://incident_url"
    incident.incident_number = "incident_number 2"
    incident.labels = [incident_labels_object, incident_labels_object, incident_labels_object]
    incident.last_activity_time_utc = datetime(2021, 9, 1, 0, 0, 2, 0, tzinfo=UTC)
    incident.last_modified_time_utc = datetime(2021, 9, 1, 0, 0, 3, 0, tzinfo=UTC)
    incident.owner = incident_owner_object
    incident.related_alert_ids = ["12E2837E", "12E2837E", "12E2837E"]
    incident.severity = "severity 2"
    incident.status = "status 2"
    incident.title = "title 2"
    return incident


@pytest.fixture
def incidents_list(first_incident_item, second_incident_item):
    return [first_incident_item, second_incident_item]


def test_to_RFC3339(trigger):
    assert trigger._to_RFC3339(datetime(2021, 9, 1, 0, 0, 0)) == "2021-09-01T00:00:00.000000Z"
    assert trigger._to_RFC3339(datetime(2021, 9, 1, 0, 0, 0, 1)) == "2021-09-01T00:00:00.000001Z"
    assert trigger._to_RFC3339(datetime(2021, 9, 2, 0, 0, 0, 1)) == "2021-09-02T00:00:00.000001Z"


def test_serialize_incident(trigger, first_incident_item):
    serialized_incident = trigger._serialize_incident(first_incident_item)
    assert isinstance(serialized_incident, dict)
    assert (
        serialized_incident["id"]
        == "/subscriptions/f00000000-0000-0000-0000-000000000000/resourceGroups/resource_group/providers/Microsoft.SecurityInsights/Incidents/"
    )
    assert serialized_incident["owner"]["assigned_to"] == "Joe Done"
    assert serialized_incident["additional_data"]["alerts_count"] == 3
    assert serialized_incident["labels"][0]["label_name"] == "label_name"


def test_get_incidents_without_batch(trigger, incidents_list):
    with (
        patch(
            "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._incidents_iterator"
        ) as mock_incidents_iterator,
        patch(
            "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._get_incident_entities"
        ) as mock_get_incident_entities,
    ):
        mock_incidents_iterator.return_value = incidents_list
        mock_get_incident_entities.return_value = [{"id": "dummy_entity_id"}]

        trigger.get_incidents()
        results = [c.kwargs["events"] for c in trigger.push_events_to_intakes.call_args_list]

        assert len(results[0]) == 2

        assert mock_get_incident_entities.call_count == len(incidents_list)
        assert mock_get_incident_entities.call_args_list == [call(incident.name) for incident in incidents_list]

        parsed_first = orjson.loads(results[0][0])
        assert parsed_first["title"] == "title"
        assert parsed_first["entities"] == [{"id": "dummy_entity_id"}]

        parsed_second = orjson.loads(results[0][1])
        assert parsed_second["title"] == "title 2"
        assert parsed_second["entities"] == [{"id": "dummy_entity_id"}]


def test_get_incident_entities_coverage(trigger):
    from unittest.mock import MagicMock

    from azure.core.exceptions import AzureError

    class EntityAsDict:
        def as_dict(self):
            return {"type": "as_dict"}

    mock_response = MagicMock()
    mock_response.entities = [EntityAsDict()]

    trigger.client = MagicMock()
    trigger.client.incidents.list_entities.return_value = mock_response

    res = trigger._get_incident_entities("inc1")
    assert len(res) == 1
    assert res[0] == {"type": "as_dict"}

    # Azure errors are handled
    trigger.client.incidents.list_entities.side_effect = AzureError("azure_err")
    assert trigger._get_incident_entities("inc1") == []

    # Test None / no entities
    mock_response_empty = MagicMock()
    mock_response_empty.entities = []

    # Test when response has no entities attribute at all
    mock_response_no_entities = MagicMock()
    del mock_response_no_entities.entities
    trigger.client.incidents.list_entities.side_effect = None
    trigger.client.incidents.list_entities.return_value = mock_response_no_entities
    assert trigger._get_incident_entities("inc1") == []
    trigger.client.incidents.list_entities.return_value = mock_response_empty
    assert trigger._get_incident_entities("inc1") == []


def test_run_method_coverage(trigger):
    from requests.exceptions import HTTPError

    # We will control the while loop by changing trigger._stop_event to True after one iteration
    def mock_get_incidents():
        trigger._stop_event.set()

    trigger.get_incidents = mock_get_incidents

    # normal run
    trigger._stop_event.clear()
    trigger.run()

    # HTTPError run
    def mock_get_incidents_http():
        trigger._stop_event.set()
        raise HTTPError("http error")

    trigger.get_incidents = mock_get_incidents_http
    trigger._stop_event.clear()
    trigger.run()

    # Exception run
    def mock_get_incidents_err():
        trigger._stop_event.set()
        raise Exception("generic error")

    trigger.get_incidents = mock_get_incidents_err
    trigger._stop_event.clear()

    import pytest

    with pytest.raises(Exception):
        trigger.run()


def test_get_incidents_persists_checkpoint(trigger, incidents_list, symphony_storage):
    most_recent = datetime.now(UTC) - timedelta(hours=1)
    incidents_list[0].last_modified_time_utc = most_recent - timedelta(minutes=5)
    incidents_list[1].last_modified_time_utc = most_recent

    with (
        patch(
            "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._incidents_iterator"
        ) as mock_incidents_iterator,
        patch(
            "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._get_incident_entities"
        ) as mock_get_incident_entities,
    ):
        mock_incidents_iterator.return_value = incidents_list
        mock_get_incident_entities.return_value = []

        trigger.get_incidents()

    assert trigger.push_events_to_intakes.called
    assert trigger.from_date == most_recent

    from microsoft_sentinel.metrics import EVENTS_LAG

    assert 3590 <= EVENTS_LAG.labels(intake_key="0123456789")._value.get() <= 3610

    # a new connector instance on the same data path resumes from the persisted checkpoint
    new_trigger = MicrosoftSentineldConnector(module=MicrosoftSentinelModule(), data_path=symphony_storage)
    assert new_trigger.cursor.offset == most_recent
    assert new_trigger.from_date == most_recent


def test_run_stops_promptly_while_waiting(trigger):
    import threading
    import time

    calls = []

    def mock_get_incidents():
        calls.append(1)

    trigger.get_incidents = mock_get_incidents
    trigger.configuration.frequency = 600

    thread = threading.Thread(target=trigger.run)
    start = time.monotonic()
    thread.start()
    time.sleep(0.2)
    trigger.stop()
    thread.join(timeout=5)

    assert not thread.is_alive()
    assert time.monotonic() - start < 5
    assert calls == [1]


@pytest.mark.parametrize(("chunk_size", "expected"), [(2, 2), (1000, 1000), (5000, 1000), (0, 1), (-3, 1)])
def test_batch_limit(trigger, chunk_size, expected):
    trigger.configuration.chunk_size = chunk_size
    assert trigger.batch_limit == expected


def test_get_incidents_batches_by_chunk_size(trigger, incidents_list, first_incident_item):
    import copy

    third = copy.deepcopy(first_incident_item)
    third.name = "third"
    incidents = [*incidents_list, third]

    with (
        patch(
            "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._incidents_iterator"
        ) as mock_incidents_iterator,
        patch(
            "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._get_incident_entities"
        ) as mock_get_incident_entities,
    ):
        mock_incidents_iterator.return_value = incidents
        mock_get_incident_entities.return_value = []

        trigger.get_incidents()

    # chunk_size is 2 in the fixture
    assert [len(c.kwargs["events"]) for c in trigger.push_events_to_intakes.call_args_list] == [2, 1]


def test_to_RFC3339_converts_to_utc(trigger):
    from datetime import timezone

    paris_summer = timezone(timedelta(hours=2))
    assert trigger._to_RFC3339(datetime(2021, 9, 1, 2, 0, 0, tzinfo=paris_summer)) == "2021-09-01T00:00:00.000000Z"
    assert trigger._to_RFC3339(datetime(2021, 9, 1, 0, 0, 0, tzinfo=UTC)) == "2021-09-01T00:00:00.000000Z"
    # naive datetimes are considered as UTC
    assert trigger._to_RFC3339(datetime(2021, 9, 1, 0, 0, 0)) == "2021-09-01T00:00:00.000000Z"
    assert trigger._to_RFC3339(None) is None


def test_get_incidents_empty(trigger):
    from microsoft_sentinel.metrics import EVENTS_LAG

    EVENTS_LAG.labels(intake_key="0123456789").set(42)
    initial_offset = trigger.cursor.offset

    with patch(
        "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._incidents_iterator"
    ) as mock_incidents_iterator:
        mock_incidents_iterator.return_value = iter([])
        trigger.get_incidents()

    trigger.push_events_to_intakes.assert_not_called()
    assert EVENTS_LAG.labels(intake_key="0123456789")._value.get() == 0
    assert trigger.cursor.offset == initial_offset


def test_get_incidents_consumes_iterator_once(trigger, incidents_list):
    # the incidents iterator is a one-shot pager: every item must be forwarded, including the first one
    with (
        patch(
            "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._incidents_iterator"
        ) as mock_incidents_iterator,
        patch(
            "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._get_incident_entities"
        ) as mock_get_incident_entities,
    ):
        mock_incidents_iterator.return_value = iter(incidents_list)
        mock_get_incident_entities.return_value = []
        trigger.get_incidents()

    assert mock_incidents_iterator.call_count == 1
    assert sum(len(c.kwargs["events"]) for c in trigger.push_events_to_intakes.call_args_list) == 2


def test_entities_azure_error_forwards_incident_and_counts(trigger, first_incident_item):
    from unittest.mock import MagicMock

    from azure.core.exceptions import AzureError

    from microsoft_sentinel.metrics import ENTITIES_FETCH_ERRORS

    counter = ENTITIES_FETCH_ERRORS.labels(intake_key="0123456789")
    errors_before = counter._value.get()

    trigger.client = MagicMock()
    trigger.client.incidents.list_entities.side_effect = AzureError("boom")

    with patch(
        "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._incidents_iterator"
    ) as mock_incidents_iterator:
        mock_incidents_iterator.return_value = [first_incident_item]
        trigger.get_incidents()

    events = [e for c in trigger.push_events_to_intakes.call_args_list for e in c.kwargs["events"]]
    assert len(events) == 1
    assert orjson.loads(events[0])["entities"] == []
    assert counter._value.get() == errors_before + 1
    warnings = [c for c in trigger.log.call_args_list if c.kwargs.get("level") == "warning"]
    assert any(first_incident_item.name in c.kwargs["message"] for c in warnings)


def test_entities_unexpected_error_propagates(trigger, first_incident_item):
    from unittest.mock import MagicMock

    trigger.client = MagicMock()
    trigger.client.incidents.list_entities.side_effect = ValueError("bug")

    with patch(
        "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._incidents_iterator"
    ) as mock_incidents_iterator:
        mock_incidents_iterator.return_value = [first_incident_item]
        with pytest.raises(ValueError, match="bug"):
            trigger.get_incidents()

    trigger.push_events_to_intakes.assert_not_called()


def make_incident(base, name, last_modified, status="New"):
    import copy

    incident = copy.deepcopy(base)
    incident.name = name
    incident.last_modified_time_utc = last_modified
    incident.status = status
    return incident


def poll(connector, incidents):
    connector.push_events_to_intakes.reset_mock()
    with (
        patch(
            "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._incidents_iterator"
        ) as mock_incidents_iterator,
        patch(
            "microsoft_sentinel.connector_microsoft_sentinel.MicrosoftSentineldConnector._get_incident_entities"
        ) as mock_get_incident_entities,
    ):
        mock_incidents_iterator.return_value = iter(incidents)
        mock_get_incident_entities.return_value = []
        connector.get_incidents()
    return [
        (event["name"], event["status"])
        for c in connector.push_events_to_intakes.call_args_list
        for event in map(orjson.loads, c.kwargs["events"])
    ]


def test_incidents_iterator_filters_and_orders_on_last_modified(trigger):
    from unittest.mock import MagicMock

    trigger.client = MagicMock()
    trigger.from_date = datetime(2021, 9, 1, 2, 0, 0, tzinfo=timezone_plus_2())

    trigger._incidents_iterator()

    trigger.client.incidents.list.assert_called_once_with(
        resource_group_name="resource_group",
        workspace_name="workspace_name",
        filter="properties/lastModifiedTimeUtc ge 2021-09-01T00:00:00.000000Z",
        orderby="properties/lastModifiedTimeUtc asc",
    )


def timezone_plus_2():
    from datetime import timezone

    return timezone(timedelta(hours=2))


def test_boundary_incidents_are_deduplicated(trigger, first_incident_item):
    t1 = datetime.now(UTC) - timedelta(minutes=10)
    t2 = t1 + timedelta(minutes=1)
    a = make_incident(first_incident_item, "A", t1)
    b = make_incident(first_incident_item, "B", t2)
    c = make_incident(first_incident_item, "C", t2)

    assert poll(trigger, [a, b]) == [("A", "New"), ("B", "New")]
    assert trigger.cursor.offset == t2

    # `ge` on the checkpoint returns B again, and C shares the boundary timestamp but was not visible before
    assert poll(trigger, [b, c]) == [("C", "New")]
    assert trigger.cursor.offset == t2

    # nothing new: no push, no lag
    assert poll(trigger, [b, c]) == []
    trigger.push_events_to_intakes.assert_not_called()


def test_duplicate_version_in_same_poll_is_forwarded_once(trigger, first_incident_item):
    t1 = datetime.now(UTC) - timedelta(minutes=10)
    a = make_incident(first_incident_item, "A", t1)
    assert poll(trigger, [a, a]) == [("A", "New")]


def test_updated_incident_is_forwarded_again(trigger, first_incident_item):
    t1 = datetime.now(UTC) - timedelta(minutes=10)
    t2 = t1 + timedelta(minutes=1)
    a = make_incident(first_incident_item, "A", t1)
    a_updated = make_incident(first_incident_item, "A", t2, status="Active")

    assert poll(trigger, [a]) == [("A", "New")]
    assert poll(trigger, [a, a_updated]) == [("A", "Active")]
    assert trigger.cursor.offset == t2


def test_boundary_dedup_survives_restart(trigger, first_incident_item, symphony_storage):
    t1 = datetime.now(UTC) - timedelta(minutes=10)
    a = make_incident(first_incident_item, "A", t1)
    b = make_incident(first_incident_item, "B", t1)
    c = make_incident(first_incident_item, "C", t1)
    assert poll(trigger, [a, b]) == [("A", "New"), ("B", "New")]

    restarted = MicrosoftSentineldConnector(module=trigger.module, data_path=symphony_storage)
    restarted.configuration = trigger.configuration
    restarted.push_events_to_intakes = Mock()
    restarted.log = Mock()
    restarted.log_exception = Mock()

    assert restarted.from_date == t1
    assert poll(restarted, [a, b, c]) == [("C", "New")]


def test_checkpoint_advanced_per_batch(trigger, first_incident_item, symphony_storage):
    t0 = datetime.now(UTC) - timedelta(minutes=10)
    incidents = [make_incident(first_incident_item, name, t0 + timedelta(seconds=i)) for i, name in enumerate("ABCDE")]

    offsets_at_push = []

    def push(events):
        offsets_at_push.append(trigger.cursor.offset)
        if len(offsets_at_push) == 2:
            raise RuntimeError("intake unavailable")
        return ["id"] * len(events)

    trigger.push_events_to_intakes = Mock(side_effect=push)

    # chunk_size is 2: batch [A, B] is pushed, batch [C, D] fails
    with pytest.raises(RuntimeError):
        poll(trigger, incidents)

    # the checkpoint was persisted after the first batch, before pushing the second one
    assert offsets_at_push[1] == t0 + timedelta(seconds=1)
    assert trigger.cursor.offset == t0 + timedelta(seconds=1)

    # a restarted connector resumes after B and does not re-send A nor B
    restarted = MicrosoftSentineldConnector(module=trigger.module, data_path=symphony_storage)
    restarted.configuration = trigger.configuration
    restarted.push_events_to_intakes = Mock()
    restarted.log = Mock()
    restarted.log_exception = Mock()
    assert restarted.from_date == t0 + timedelta(seconds=1)
    # `ge` returns B again (boundary), then C, D, E
    assert poll(restarted, incidents[1:]) == [("C", "New"), ("D", "New"), ("E", "New")]
    assert restarted.cursor.offset == t0 + timedelta(seconds=4)
