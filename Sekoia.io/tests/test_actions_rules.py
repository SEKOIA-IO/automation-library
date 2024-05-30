from urllib.parse import unquote as url_decoder

import pytest
import requests_mock

from sekoiaio.operation_center import GetRule, EnableRule, DisableRule, DeleteRule, CreateRule, UpdateRule

module_base_url = "http://fake.url/"
base_url = module_base_url + "api/v1/sic/"
apikey = "fake_api_key"


def test_enable_rule_success():

  action: EnableRule = EnableRule()
  action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

  ressource = "rules-catalog/rules/fake_uuid"
  expected_response = {"message": "Rule enabled successfully"}
  arguments = {"uuid": "fake_uuid"}

  with requests_mock.Mocker() as mock:
    mock.put(f"{base_url}{ressource}/enable", json=expected_response)
    results: dict = action.run(arguments)

    assert results == expected_response
    assert mock.call_count == 1
    history = mock.request_history
    assert history[0].method == "PUT"
    assert url_decoder(history[0].url) == f"{base_url}{ressource}/enable"


def test_disable_rule_success():

  action: DisableRule = DisableRule()
  action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

  ressource = "rules-catalog/rules/fake_uuid"
  expected_response = {"message": "Rule disabled successfully"}
  arguments = {"uuid": "fake_uuid"}

  with requests_mock.Mocker() as mock:
    mock.put(f"{base_url}{ressource}/disable", json=expected_response)
    results: dict = action.run(arguments)

    assert results == expected_response
    assert mock.call_count == 1
    history = mock.request_history
    assert history[0].method == "PUT"
    assert url_decoder(history[0].url) == f"{base_url}{ressource}/disable"


def test_delete_rule_success():

  action: DeleteRule = DeleteRule()
  action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

  ressource = "rules-catalog/rules/fake_uuid"
  expected_response = {"message": "Rule deleted successfully"}
  arguments = {"uuid": "fake_uuid"}

  with requests_mock.Mocker() as mock:
    mock.delete(f"{base_url}{ressource}", json=expected_response)
    results: dict = action.run(arguments)

    assert results == expected_response
    assert mock.call_count == 1
    history = mock.request_history
    assert history[0].method == "DELETE"
    assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_create_rule_success():

  action: CreateRule = CreateRule()
  action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

  ressource = "rules-catalog/rules"
  expected_response = {"message": "Rule created successfully"}
  arguments = {
    "name": "New Rule",
    "description": "This is a new rule",
    "payload": "payload",
    "severity": 1,
    "effort": 2,
    "alert_type_uuid": "alert_type_uuid",
    "alert_category_uuid": "alert_category_uuid",
    "tags": ["tag1", "tag2"],
    "source": "source",
    "verified": True,
    "related_object_refs": ["ref1", "ref2"],
    "datasources": ["datasource1", "datasource2"],
    "event_fields": [{"field": "field1", "description": "description1"}, {"field": "field2", "description": "description2"}],
    "similarity_strategy": [None],
    "goal": "goal",
    "false_positives": "false_positives",
    "references": "references",
    "available_for_subcommunities": False,
    "instance_uuid": "instance_uuid"
  }

  with requests_mock.Mocker() as mock:
    mock.post(f"{base_url}{ressource}", json=expected_response)
    results: dict = action.run(arguments)

    assert results == expected_response
    assert mock.call_count == 1
    history = mock.request_history
    assert history[0].method == "POST"
    assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_update_rule_success():

  action: UpdateRule = UpdateRule()
  action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

  ressource = "rules-catalog/rules/fake_uuid"
  expected_response = {"message": "Rule updated successfully"}
  arguments = {
    "uuid": "fake_uuid",
    "name": "Updated Rule",
    "description": "This rule has been updated",
    "payload": "updated_payload",
    "severity": 2,
    "effort": 3,
    "alert_type_uuid": "updated_alert_type_uuid",
    "alert_category_uuid": "updated_alert_category_uuid",
    "tags": ["tag1", "tag2", "tag3"],
    "source": "updated_source",
    "verified": False,
    "related_object_refs": ["ref1", "ref2", "ref3"],
    "datasources": ["datasource1", "datasource2", "datasource3"],
    "event_fields": [{"field": "field1", "description": "description1"}, {"field": "field2", "description": "description2"}, {"field": "field3", "description": "description3"}],
    "similarity_strategy": [None],
    "goal": "updated_goal",
    "false_positives": "updated_false_positives",
    "references": "updated_references",
    "available_for_subcommunities": True,
    "instance_uuid": "updated_instance_uuid"
  }

  with requests_mock.Mocker() as mock:
    mock.put(f"{base_url}{ressource}", json=expected_response)
    results: dict = action.run(arguments)

    assert results == expected_response
    assert mock.call_count == 1
    history = mock.request_history
    assert history[0].method == "PUT"
    assert url_decoder(history[0].url) == f"{base_url}{ressource}"
