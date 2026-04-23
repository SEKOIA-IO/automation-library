import pytest
import orjson
from datetime import datetime, timezone
from unittest.mock import Mock, patch, call


from microsoft_sentinel import MicrosoftSentinelModule
from microsoft_sentinel.connector_microsoft_sentinel import MicrosoftSentineldConnector
from azure.mgmt.securityinsight.models import Incident, IncidentAdditionalData, IncidentOwnerInfo, IncidentLabel


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
    incident.created_time_utc = datetime(2021, 9, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
    incident.description = "description"
    incident.first_activity_time_utc = datetime(2021, 9, 1, 0, 0, 1, 0, tzinfo=timezone.utc)
    incident.incident_url = "https://incident_url"
    incident.incident_number = "incident_number"
    incident.labels = [incident_labels_object, incident_labels_object, incident_labels_object]
    incident.last_activity_time_utc = datetime(2021, 9, 1, 0, 0, 2, 0, tzinfo=timezone.utc)
    incident.last_modified_time_utc = datetime(2021, 9, 1, 0, 0, 3, 0, tzinfo=timezone.utc)
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
    incident.name = "7f744677-21e3-42c9"
    incident.type = "Microsoft.SecurityInsights/Incidents"
    incident.system_data = None
    incident.etag = "00000000-0000-0000-0000-000000000000"
    incident.additional_data = additional_data_object
    incident.classification = None
    incident.classification_comment = None
    incident.classification_reason = None
    incident.created_time_utc = datetime(2021, 9, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
    incident.description = "description 2"
    incident.first_activity_time_utc = datetime(2021, 9, 1, 0, 0, 1, 0, tzinfo=timezone.utc)
    incident.incident_url = "https://incident_url"
    incident.incident_number = "incident_number 2"
    incident.labels = [incident_labels_object, incident_labels_object, incident_labels_object]
    incident.last_activity_time_utc = datetime(2021, 9, 1, 0, 0, 2, 0, tzinfo=timezone.utc)
    incident.last_modified_time_utc = datetime(2021, 9, 1, 0, 0, 3, 0, tzinfo=timezone.utc)
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
    assert type(serialized_incident) == dict
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
    from azure.core.exceptions import AzureError
    from unittest.mock import MagicMock

    # Case 1: as_dict
    class EntityAsDict:
        def as_dict(self):
            return {"type": "as_dict"}

    # Case 2: serialize
    class EntitySerialize:
        def serialize(self):
            return {"type": "serialize"}

    # Case 3: dict parse
    class EntityDictParse:
        def __iter__(self):
            yield "type", "dict_parse"

    # Case 4: Exception type
    class EntityDictError:
        pass

    entity_dict = {"type": "dict"}

    mock_response = MagicMock()
    mock_response.entities = [EntityAsDict(), EntitySerialize(), entity_dict, EntityDictParse(), EntityDictError()]

    trigger.client = MagicMock()
    trigger.client.incidents.list_entities.return_value = mock_response

    res = trigger._get_incident_entities("inc1")
    assert len(res) == 4
    assert res[0] == {"type": "as_dict"}
    assert res[1] == {"type": "serialize"}
    assert res[2] == {"type": "dict"}
    assert res[3] == {"type": "dict_parse"}

    # Test exceptions
    trigger.client.incidents.list_entities.side_effect = AzureError("azure_err")
    assert trigger._get_incident_entities("inc1") == []

    trigger.client.incidents.list_entities.side_effect = Exception("err")
    assert trigger._get_incident_entities("inc1") == []

    # Test None / no entities
    mock_response_empty = MagicMock()
    del mock_response_empty.entities
    trigger.client.incidents.list_entities.side_effect = None
    trigger.client.incidents.list_entities.return_value = mock_response_empty
    assert trigger._get_incident_entities("inc1") == []
