import pytest
import json
from urllib.parse import urljoin
from pydantic import BaseModel
from typing import List, Dict, Any

# Adjust the import path according to your project structure
from sekoiaio.operation_center.synchronize_assets_with_ad import (
    SynchronizeAssetsWithAD,
    Arguments,
    Action,
)


# Mock Module class to provide configuration to the action
class MockModule:
    def __init__(self, configuration: Dict[str, Any]):
        self.configuration = configuration


# Test class
class TestSynchronizeAssetsWithAD:
    @pytest.fixture
    def action_instance(self):
        """
        Fixture to create an instance of the SynchronizeAssetsWithAD action
        with a mocked module configuration.
        """
        configuration = {
            "base_url": "https://api.example.com",
            "api_key": "test_api_key",
        }
        module = MockModule(configuration=configuration)
        action = SynchronizeAssetsWithAD()
        action.module = module
        return action

    @pytest.fixture
    def arguments(self):
        """
        Fixture to provide the necessary arguments for running the action.
        """
        return Arguments(
            user_ad_data={
                "username": "jdoe",
                "email": "jdoe@example.com",
                "department": "engineering",
            },
            asset_synchronization_configuration={
                "asset_name_field": "username",
                "detection_properties": {
                    "email": ["email"],
                    "department": ["department"],
                },
                "contextual_properties": {
                    "dept": "department",
                },
            },
            community_uuid="community-1234",
        )

    def test_no_asset_found_and_create(self, requests_mock, action_instance, arguments):
        """
        Test the SynchronizeAssetsWithAD action for the scenario where multiple assets are found,
        and one of them is edited while merging the others.
        """
        # Extract configuration from the mock module
        base_url = action_instance.module.configuration["base_url"]
        api_key = action_instance.module.configuration["api_key"]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        # URLs
        assets_url = urljoin(base_url + "/", "v2/asset-management/assets")
        merge_url = urljoin(base_url + "/", "v2/asset-management/assets/merge")
        update_url = urljoin(base_url + "/", "v2/asset-management/assets/asset-uuid-1")
        create_url = urljoin(base_url + "/", "v2/asset-management/assets")

        # Helper functions to match specific GET requests
        def match_asset_name(request):
            search_query = request.qs.get("search", [None])[0]
            also_search = "also_search_in_detection_properties" in request.qs
            return search_query == "jdoe" and not also_search

        def match_detection_properties(request):
            return request.qs.get("also_search_in_detection_properties", [None])[0] == "true"

        # Mock GET request for asset name search (should return one asset)
        requests_mock.get(
            assets_url,
            additional_matcher=match_asset_name,
            json={
                "total": 0,
                "items": [],
            },
            status_code=200,
        )

        # Mock GET request for detection properties (should return two additional assets)
        requests_mock.get(
            assets_url,
            additional_matcher=match_detection_properties,
            json={
                "total": 0,
                "items": [],
            },
            status_code=200,
        )

        # Mock PUT request to update the destination asset
        requests_mock.post(
            create_url,
            json={"uuid": "asset_uuid_in_response"},  # Assume successful update with empty response
            status_code=200,
        )

        # Execute the action
        response = action_instance.run(arguments)

        # Assertions
        assert response["created_asset"] is True, "Asset should not be created since it exists."
        assert response["destination_asset"] == "asset_uuid_in_response", "Destination asset UUID mismatch."
        assert set(response["found_assets"]) == set(), "Found assets mismatch."

        # Verify that the correct number of requests were made
        # Expected Requests:
        # 1. GET asset name search
        # 2. 2 GET for all the detection properties search
        # 3. PUT update asset
        # 4. POST merge assets
        assert (
            len(requests_mock.request_history) == 4
        ), f"Expected 4 HTTP requests, got {len(requests_mock.request_history)}."

        # Optionally, verify the payloads of PUT and POST requests
        # Verify PUT request payload
        post_requests = [req for req in requests_mock.request_history if req.method == "POST"]
        assert len(post_requests) == 1, "Expected one POST request."
        post_request = post_requests[0]
        expected_post_payload = {
            'name': 'jdoe',
            'description': '',
            'type': 'account',
            'category': 'user',
            'reviewed': True,
            'source': 'manual',
            'props': {'dept': 'engineering'},
            'atoms': {'email': ['jdoe@example.com'], 'department': ['engineering']},
            'community_uuid': 'community-1234',
        }
        assert post_request.json() == expected_post_payload, "POST request payload mismatch."

    def test_one_asset_found_and_merge(self, requests_mock, action_instance, arguments):
        """
        Test the SynchronizeAssetsWithAD action for the scenario where multiple assets are found,
        and one of them is edited while merging the others.
        """
        # Extract configuration from the mock module
        base_url = action_instance.module.configuration["base_url"]
        api_key = action_instance.module.configuration["api_key"]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        # URLs
        assets_url = urljoin(base_url + "/", "v2/asset-management/assets")
        merge_url = urljoin(base_url + "/", "v2/asset-management/assets/merge")
        update_url = urljoin(base_url + "/", "v2/asset-management/assets/asset-uuid-1")
        create_url = urljoin(base_url + "/", "v2/asset-management/assets")

        # Helper functions to match specific GET requests
        def match_asset_name(request):
            search_query = request.qs.get("search", [None])[0]
            also_search = "also_search_in_detection_properties" in request.qs
            return search_query == "jdoe" and not also_search

        def match_detection_properties(request):
            return request.qs.get("also_search_in_detection_properties", [None])[0] == "true"

        # Mock GET request for asset name search (should return one asset)
        requests_mock.get(
            assets_url,
            additional_matcher=match_asset_name,
            json={
                "total": 1,
                "items": [{"uuid": "asset-uuid-1", "name": "jdoe", "atoms": []}],
            },
            status_code=200,
        )

        # Mock GET request for detection properties (should return two additional assets)
        requests_mock.get(
            assets_url,
            additional_matcher=match_detection_properties,
            json={
                "total": 0,
                "items": [],
            },
            status_code=200,
        )

        # Mock PUT request to update the destination asset
        requests_mock.put(
            update_url,
            json={},  # Assume successful update with empty response
            status_code=200,
        )

        # Execute the action
        response = action_instance.run(arguments)

        # Assertions
        assert response["created_asset"] is False, "Asset should not be created since it exists."
        assert response["destination_asset"] == "asset-uuid-1", "Destination asset UUID mismatch."
        assert set(response["found_assets"]) == {"asset-uuid-1"}, "Found assets mismatch."

        # Verify that the correct number of requests were made
        # Expected Requests:
        # 1. GET asset name search
        # 2. 2 GET for all the detection properties search
        # 3. PUT update asset
        # 4. POST merge assets
        assert (
            len(requests_mock.request_history) == 4
        ), f"Expected 4 HTTP requests, got {len(requests_mock.request_history)}."

        # Optionally, verify the payloads of PUT and POST requests
        # Verify PUT request payload
        put_requests = [req for req in requests_mock.request_history if req.method == "PUT"]
        assert len(put_requests) == 1, "Expected one PUT request."
        put_request = put_requests[0]
        expected_put_payload = {
            'name': 'jdoe',
            'description': '',
            'type': 'account',
            'category': 'user',
            'reviewed': True,
            'source': 'manual',
            'props': {'dept': 'engineering'},
            'atoms': {'email': ['jdoe@example.com'], 'department': ['engineering']},
        }
        assert put_request.json() == expected_put_payload, "PUT request payload mismatch."

    def test_multiple_assets_found_and_merge(self, requests_mock, action_instance, arguments):
        """
        Test the SynchronizeAssetsWithAD action for the scenario where multiple assets are found,
        and one of them is edited while merging the others.
        """
        # Extract configuration from the mock module
        base_url = action_instance.module.configuration["base_url"]
        api_key = action_instance.module.configuration["api_key"]

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        # URLs
        assets_url = urljoin(base_url + "/", "v2/asset-management/assets")
        merge_url = urljoin(base_url + "/", "v2/asset-management/assets/merge")
        update_url = urljoin(base_url + "/", "v2/asset-management/assets/asset-uuid-1")
        create_url = urljoin(base_url + "/", "v2/asset-management/assets")

        # Helper functions to match specific GET requests
        def match_asset_name(request):
            search_query = request.qs.get("search", [None])[0]
            also_search = "also_search_in_detection_properties" in request.qs
            return search_query == "jdoe" and not also_search

        def match_detection_properties(request):
            return request.qs.get("also_search_in_detection_properties", [None])[0] == "true"

        # Mock GET request for asset name search (should return one asset)
        requests_mock.get(
            assets_url,
            additional_matcher=match_asset_name,
            json={
                "total": 1,
                "items": [{"uuid": "asset-uuid-1", "name": "jdoe", "atoms": []}],
            },
            status_code=200,
        )

        # Mock GET request for detection properties (should return two additional assets)
        requests_mock.get(
            assets_url,
            additional_matcher=match_detection_properties,
            json={
                "total": 2,
                "items": [
                    {"uuid": "asset-uuid-2", "name": "asset2", "atoms": []},
                    {"uuid": "asset-uuid-3", "name": "asset3", "atoms": []},
                ],
            },
            status_code=200,
        )

        # Mock PUT request to update the destination asset
        requests_mock.put(
            update_url,
            json={},  # Assume successful update with empty response
            status_code=200,
        )

        # Mock POST request to merge assets
        requests_mock.post(
            merge_url,
            json={},  # Assume successful merge with empty response
            status_code=200,
        )

        # Execute the action
        response = action_instance.run(arguments)

        # Assertions
        assert response["created_asset"] is False, "Asset should not be created since it exists."
        assert response["destination_asset"] == "asset-uuid-1", "Destination asset UUID mismatch."
        assert set(response["found_assets"]) == {
            "asset-uuid-1",
            "asset-uuid-2",
            "asset-uuid-3",
        }, "Found assets mismatch."

        # Verify that the correct number of requests were made
        # Expected Requests:
        # 1. GET asset name search
        # 2. 2 GET for all the detection properties search
        # 3. PUT update asset
        # 4. POST merge assets
        assert (
            len(requests_mock.request_history) == 5
        ), f"Expected 5 HTTP requests, got {len(requests_mock.request_history)}."

        # Optionally, verify the payloads of PUT and POST requests
        # Verify PUT request payload
        put_requests = [req for req in requests_mock.request_history if req.method == "PUT"]
        assert len(put_requests) == 1, "Expected one PUT request."
        put_request = put_requests[0]
        expected_put_payload = {
            'name': 'jdoe',
            'description': '',
            'type': 'account',
            'category': 'user',
            'reviewed': True,
            'source': 'manual',
            'props': {'dept': 'engineering'},
            'atoms': {'email': ['jdoe@example.com'], 'department': ['engineering']},
        }
        assert put_request.json() == expected_put_payload, "PUT request payload mismatch."

        # Verify POST merge request payload
        post_merge_requests = [
            req for req in requests_mock.request_history if req.method == "POST" and req.url.endswith("/merge")
        ]
        assert len(post_merge_requests) == 1, "Expected one POST merge request."
        post_merge = post_merge_requests[0].json()
        expected_merge_payload = {
            "destination": "asset-uuid-1",
            "sources": ["asset-uuid-3", "asset-uuid-2"],
        }
        # Assert 'destination' field is equal
        assert post_merge["destination"] == expected_merge_payload["destination"], "Destination mismatch."

        # Assert 'sources' list contains the same elements, regardless of order
        assert set(post_merge["sources"]) == set(expected_merge_payload["sources"]), "Sources mismatch."

    # def test_one_asset_found_and_merge_testapp(self):
    #     # Extract configuration from the mock module
    #     base_url = "https://app.test.sekoia.io"
    #     api_key = "TO_ADD"

    #     app_test_arg = Arguments( # TO COMPLETE
    #         user_ad_data={},
    #         asset_synchronization_configuration={},
    #         community_uuid="",
    #     )

    #     configuration = {
    #         "base_url": base_url,
    #         "api_key": api_key,
    #     }
    #     module = MockModule(configuration=configuration)
    #     action = SynchronizeAssetsWithAD()
    #     action.module = module
    #     # Execute the action
    #     response = action.run(app_test_arg)
