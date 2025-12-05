from urllib.parse import unquote as url_decoder

import requests_mock
from tenacity import wait_none
from sekoiaio.operation_center import GetRule, EnableRule, DisableRule, DeleteRule, CreateRule, UpdateRule

module_base_url = "http://fake.url/"
base_url = module_base_url + "api/v1/sic/"
apikey = "fake_api_key"


def test_get_rule_success():
    action: GetRule = GetRule()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "conf/rules-catalog/rules/fake_uuid"
    expected_response = {
        "uuid": "fake_uuid",
        "name": "Rule Name",
        "enabled": True,
        "description": "Rule Description",
        "payload": "rule_payload",
        "severity": 1,
        "effort": 2,
        "alert_type_uuid": "alert_type_uuid",
        "alert_category_uuid": "alert_category_uuid",
        "tags": ["tag1", "tag2"],
        "source": "source",
        "verified": True,
        "related_object_refs": ["ref1", "ref2"],
        "datasources": ["datasource1", "datasource2"],
        "event_fields": [
            {"field": "field1", "description": "description1"},
            {"field": "field2", "description": "description2"},
        ],
        "similarity_strategy": [None],
        "goal": "goal",
        "false_positives": "false_positives",
        "references": "references",
        "available_for_subcommunities": False,
        "instance_uuid": "instance_uuid",
    }
    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=expected_response)
        results: dict = action.run({"uuid": "fake_uuid"})
        assert results == expected_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_enable_rule_failure():
    action: EnableRule = EnableRule()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    action._wait_param = lambda: wait_none()

    ressource = "conf/rules-catalog/rules/fake_uuid"
    expected_response = None
    arguments = {"uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.put(f"{base_url}{ressource}/enabled", json=expected_response, status_code=500)
        results: dict = action.run(arguments)
        assert results == expected_response
        history = mock.request_history
        assert history[0].method == "PUT"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}/enabled"


def test_get_rule_failure():
    action: GetRule = GetRule()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    action._wait_param = lambda: wait_none()

    ressource = "conf/rules-catalog/rules/fake_uuid"
    expected_response = None
    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=expected_response, status_code=500)
        results: dict = action.run({"uuid": "fake_uuid"})
        assert results == expected_response
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_delete_rule_failure():
    action: DeleteRule = DeleteRule()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    action._wait_param = lambda: wait_none()
    ressource = "conf/rules-catalog/rules/fake_uuid"
    expected_response = None
    arguments = {"uuid": "fake_uuid"}
    with requests_mock.Mocker() as mock:
        mock.delete(f"{base_url}{ressource}", json=expected_response, status_code=500)
        results: dict = action.run(arguments)
        assert results == expected_response
        history = mock.request_history
        assert history[0].method == "DELETE"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_create_rule_failure():
    action: CreateRule = CreateRule()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    action._wait_param = lambda: wait_none()
    ressource = "conf/rules-catalog/rules"
    expected_response = None
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
        "event_fields": [
            {"field": "field1", "description": "description1"},
            {"field": "field2", "description": "description2"},
        ],
        "similarity_strategy": [None],
        "goal": "goal",
        "false_positives": "false_positives",
        "references": "references",
        "available_for_subcommunities": True,
        "instance_uuid": "instance_uuid",
    }
    with requests_mock.Mocker() as mock:
        mock.post(f"{base_url}{ressource}", json=expected_response, status_code=500)
        results: dict = action.run(arguments)
        assert results == expected_response
        history = mock.request_history
        assert history[0].method == "POST"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_update_rule_failure():
    action: UpdateRule = UpdateRule()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    action._wait_param = lambda: wait_none()
    ressource = "conf/rules-catalog/rules/fake_uuid"
    expected_response = None
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
        "verified": True,
        "related_object_refs": ["ref1", "ref2", "ref3"],
        "datasources": ["datasource1", "datasource2", "datasource3"],
        "event_fields": [
            {"field": "field1", "description": "description1"},
            {"field": "field2", "description": "description2"},
            {"field": "field3", "description": "description3"},
        ],
        "similarity_strategy": [None],
        "goal": "updated_goal",
        "false_positives": "updated_false_positives",
        "references": "updated_references",
        "available_for_subcommunities": True,
        "instance_uuid": "updated_instance_uuid",
    }
    with requests_mock.Mocker() as mock:
        mock.put(f"{base_url}{ressource}", json=expected_response, status_code=500)
        results: dict = action.run(arguments)
        assert results == expected_response
        history = mock.request_history
        assert history[0].method == "PUT"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_disable_rule_failure():
    action: DisableRule = DisableRule()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    action._wait_param = lambda: wait_none()

    ressource = "conf/rules-catalog/rules/fake_uuid"
    expected_response = None
    arguments = {"uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.put(f"{base_url}{ressource}/disabled", json=expected_response, status_code=500)
        results: dict = action.run(arguments)

        assert results == expected_response
        history = mock.request_history
        assert history[0].method == "PUT"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}/disabled"


def test_delete_rule_success():
    action: DeleteRule = DeleteRule()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}
    action._wait_param = lambda: wait_none()

    ressource = "conf/rules-catalog/rules/fake_uuid"
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

    ressource = "conf/rules-catalog/rules"
    expected_response = {
        "uuid": "fake_uuid",
        "name": "New Rule",
        "enabled": True,
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
        "event_fields": [
            {"field": "field1", "description": "description1"},
            {"field": "field2", "description": "description2"},
        ],
        "similarity_strategy": [None],
        "goal": "goal",
        "false_positives": "false_positives",
        "references": "references",
        "available_for_subcommunities": True,
        "instance_uuid": "instance_uuid",
    }
    arguments = {
        "name": "New Rule",
        "description": "This is a new rule",
        "enabled": True,
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
        "event_fields": [
            {"field": "field1", "description": "description1"},
            {"field": "field2", "description": "description2"},
        ],
        "similarity_strategy": [None],
        "goal": "goal",
        "false_positives": "false_positives",
        "references": "references",
        "available_for_subcommunities": True,
        "instance_uuid": "instance_uuid",
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

    ressource = "conf/rules-catalog/rules/fake_uuid"
    expected_response = {
        "uuid": "fake_uuid",
        "name": "Updated Rule",
        "enabled": True,
        "description": "This rule has been updated",
        "payload": "updated_payload",
        "severity": 2,
        "effort": 3,
        "alert_type_uuid": "updated_alert_type_uuid",
        "alert_category_uuid": "updated_alert_category_uuid",
        "tags": ["tag1", "tag2", "tag3"],
        "source": "updated_source",
        "verified": True,
        "related_object_refs": ["ref1", "ref2", "ref3"],
        "datasources": ["datasource1", "datasource2", "datasource3"],
        "event_fields": [
            {"field": "field1", "description": "description1"},
            {"field": "field2", "description": "description2"},
            {"field": "field3", "description": "description3"},
        ],
        "similarity_strategy": [None],
        "goal": "updated_goal",
        "false_positives": "updated_false_positives",
        "references": "updated_references",
        "available_for_subcommunities": True,
        "instance_uuid": "updated_instance_uuid",
    }
    arguments = {
        "uuid": "fake_uuid",
        "name": "Updated Rule",
        "enabled": True,
        "description": "This rule has been updated",
        "payload": "updated_payload",
        "severity": 2,
        "effort": 3,
        "alert_type_uuid": "updated_alert_type_uuid",
        "alert_category_uuid": "updated_alert_category_uuid",
        "tags": ["tag1", "tag2", "tag3"],
        "source": "updated_source",
        "verified": True,
        "related_object_refs": ["ref1", "ref2", "ref3"],
        "datasources": ["datasource1", "datasource2", "datasource3"],
        "event_fields": [
            {"field": "field1", "description": "description1"},
            {"field": "field2", "description": "description2"},
            {"field": "field3", "description": "description3"},
        ],
        "similarity_strategy": [None],
        "goal": "updated_goal",
        "false_positives": "updated_false_positives",
        "references": "updated_references",
        "available_for_subcommunities": True,
        "instance_uuid": "updated_instance_uuid",
    }

    with requests_mock.Mocker() as mock:
        mock.put(f"{base_url}{ressource}", json=expected_response)
        results: dict = action.run(arguments)

        assert results == expected_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "PUT"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"


def test_enable_rule_success():
    action: EnableRule = EnableRule()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "conf/rules-catalog/rules/fake_uuid"
    expected_response = {
        "uuid": "fake_uuid",
        "name": "Rule Name",
        "enabled": True,
        "description": "Rule Description",
        "payload": "rule_payload",
        "severity": 1,
        "effort": 2,
        "alert_type_uuid": "alert_type_uuid",
        "alert_category_uuid": "alert_category_uuid",
        "tags": ["tag1", "tag2"],
        "source": "source",
        "verified": True,
        "related_object_refs": ["ref1", "ref2"],
        "datasources": ["datasource1", "datasource2"],
        "event_fields": [
            {"field": "field1", "description": "description1"},
            {"field": "field2", "description": "description2"},
        ],
        "similarity_strategy": [None],
        "goal": "goal",
        "false_positives": "false_positives",
        "references": "references",
        "available_for_subcommunities": False,
        "instance_uuid": "instance_uuid",
    }
    arguments = {"uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.put(f"{base_url}{ressource}/enabled", json=expected_response)
        results: dict = action.run(arguments)
        assert results == expected_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "PUT"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}/enabled"


def test_disable_rule_success():
    action: DisableRule = DisableRule()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "conf/rules-catalog/rules/fake_uuid"
    expected_response = {
        "uuid": "fake_uuid",
        "name": "Rule Name",
        "enabled": False,
        "description": "Rule Description",
        "payload": "rule_payload",
        "severity": 1,
        "effort": 2,
        "alert_type_uuid": "alert_type_uuid",
        "alert_category_uuid": "alert_category_uuid",
        "tags": ["tag1", "tag2"],
        "source": "source",
        "verified": True,
        "related_object_refs": ["ref1", "ref2"],
        "datasources": ["datasource1", "datasource2"],
        "event_fields": [
            {"field": "field1", "description": "description1"},
            {"field": "field2", "description": "description2"},
        ],
        "similarity_strategy": [None],
        "goal": "goal",
        "false_positives": "false_positives",
        "references": "references",
        "available_for_subcommunities": False,
        "instance_uuid": "instance_uuid",
    }
    arguments = {"uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.put(f"{base_url}{ressource}/disabled", json=expected_response)
        results: dict = action.run(arguments)
        assert results == expected_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "PUT"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}/disabled"
