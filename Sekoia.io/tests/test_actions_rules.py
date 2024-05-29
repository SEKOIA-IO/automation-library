from urllib.parse import unquote as url_decoder

import pytest
import requests_mock

from sekoiaio.operation_center import GetRule, EnableRule, DisableRule, DeleteRule, CreateRule, UpdateRule

module_base_url = "http://fake.url/"
base_url = module_base_url + "api/v1/sic/"
apikey = "fake_api_key"


def test_get_rule_success():
    action: GetRule = GetRule()
    action.module.configuration = {"base_url": module_base_url, "api_key": apikey}

    ressource = "rules-catalog/rules/fake_uuid"
    expected_response = {
        "uuid": "string",
        "enabled": True,
        "community_uuid": "string",
        "parameters": [
            {"uuid": "string", "name": "string", "value": "string", "default": "string", "description": "string"}
        ],
        "all_entities": True,
        "entities": [
            {
                "name": "string",
                "entity_id": "string",
                "alerts_generation": "string",
                "description": "string",
                "community_uuid": "string",
                "uuid": "string",
                "number_of_intakes": 0,
            }
        ],
        "all_assets": True,
        "assets": ["string"],
        "last_compilation_success": True,
        "last_compilation_message": "string",
        "last_compilation_at": "string",
        "name": "string",
        "type": None,
        "private": True,
        "is_private": True,
        "description": "string",
        "payload": "string",
        "severity": 0,
        "effort": 0,
        "alert_type": {
            "uuid": "string",
            "category_uuid": "string",
            "value": "string",
            "detail": "string",
            "description": "string",
        },
        "alert_category": {"uuid": "string", "name": "string"},
        "tags": [{"uuid": "string", "name": "string"}],
        "source": "string",
        "verified": True,
        "related_object_refs": ["string"],
        "datasources": [{"uuid": "string", "name": "string"}],
        "event_fields": [{"field": "string", "description": "string"}],
        "similarity_strategy": [None],
        "created_at": "string",
        "created_by": "string",
        "created_by_type": "string",
        "updated_at": "string",
        "updated_by": "string",
        "updated_by_type": "string",
        "goal": "string",
        "false_positives": "string",
        "references": "string",
        "available_for_subcommunities": False,
        "instance_uuid": "string",
    }
    arguments = {"uuid": "fake_uuid"}

    with requests_mock.Mocker() as mock:
        mock.get(f"{base_url}{ressource}", json=expected_response)

        results: dict = action.run(arguments)

        assert results == expected_response
        assert mock.call_count == 1
        history = mock.request_history
        assert history[0].method == "GET"
        assert url_decoder(history[0].url) == f"{base_url}{ressource}"
