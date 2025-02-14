import pytest

from microsoft_sentinel.utils import additional_data_to_dict, owner_data_to_dict, labels_data_to_dict
from azure.mgmt.securityinsight.models import IncidentAdditionalData, IncidentOwnerInfo, IncidentLabel


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


def test_additional_data_to_dict(additional_data_object):
    additional_data_response = additional_data_to_dict(additional_data_object)
    assert type(additional_data_response) == dict
    assert additional_data_response == {
        "additional_properties": {},
        "alerts_count": 3,
        "bookmarks_count": 2,
        "comments_count": 1,
        "alert_product_names": ["alert_product_names"],
        "tactics": ["tactics"],
    }


def test_owner_data_to_dict(incident_owner_object):
    owner_data_response = owner_data_to_dict(incident_owner_object)
    assert type(owner_data_response) == dict
    assert owner_data_response == {
        "additional_properties": {},
        "assigned_to": "Joe Done",
        "email": "joe.done@gmail.com",
        "user_principal_name": "Joe Done",
        "object_id": "123456",
    }


def test_labels_data_to_dict(incident_labels_object):
    labels_data_response = labels_data_to_dict(incident_labels_object)
    assert type(labels_data_response) == dict
    assert labels_data_response.get("additional_properties") == {}
    assert labels_data_response.get("label_name") == "label_name"
    # label_type is readonly and can't be set
    assert labels_data_response.get("label_type") == None
