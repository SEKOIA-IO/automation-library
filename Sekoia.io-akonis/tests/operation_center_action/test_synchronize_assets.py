import pytest
import json
from urllib.parse import urljoin
from pydantic.v1 import BaseModel
from typing import List, Dict, Any
from unittest.mock import patch

# Adjust the import path according to your project structure
from sekoiaio.operation_center.synchronize_assets_with_ad import (
    SynchronizeAssetsWithAD,
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
        return {
            "user_ad_data": {
                "username": "jdoe",
                "email": "jdoe@example.com",
                "department": "engineering",
            },
            "asset_synchronization_configuration": {
                "asset_name_field": "username",
                "detection_properties": {
                    "email": ["email"],
                    "department": ["department"],
                },
                "contextual_properties": {
                    "dept": "department",
                },
            },
            "community_uuid": "community-1234",
        }

    @pytest.fixture
    def arguments_with_file(self):
        """
        Fixture to provide the necessary arguments for running the action
        with a user_ad_file.
        """
        return {
            "user_ad_data_path": "path/to/user_ad_file.json",
            "asset_synchronization_configuration": {
                "asset_name_field": "username",
                "detection_properties": {
                    "email": ["email"],
                    "department": ["department"],
                },
                "contextual_properties": {
                    "dept": "department",
                },
            },
            "community_uuid": "community-1234",
        }

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
        resp = action_instance.run(arguments)
        response = resp["data"][0]

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
            "name": "jdoe",
            "description": "",
            "type": "account",
            "category": "user",
            "reviewed": True,
            "source": "manual",
            "props": {"dept": "engineering"},
            "atoms": {"email": ["jdoe@example.com"], "department": ["engineering"]},
            "community_uuid": "community-1234",
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
        resp = action_instance.run(arguments)
        response = resp["data"][0]

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
            "name": "jdoe",
            "description": "",
            "type": "account",
            "category": "user",
            "reviewed": True,
            "source": "manual",
            "props": {"dept": "engineering"},
            "atoms": {"email": ["jdoe@example.com"], "department": ["engineering"]},
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
        resp = action_instance.run(arguments)
        response = resp["data"][0]

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
            "name": "jdoe",
            "description": "",
            "type": "account",
            "category": "user",
            "reviewed": True,
            "source": "manual",
            "props": {"dept": "engineering"},
            "atoms": {"email": ["jdoe@example.com"], "department": ["engineering"]},
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

    def test_using_user_ad_file(self, requests_mock, action_instance, arguments_with_file):
        """
        Test the SynchronizeAssetsWithAD action using user_ad_file to provide user AD data.
        """
        # Define the mock user AD data to be returned when reading the file
        mock_user_ad_data = [
            {
                "username": "asmith",
                "email": "asmith@example.com",
                "department": "marketing",
            },
            {
                "username": "bjones",
                "email": "bjones@example.com",
                "department": "sales",
            },
        ]

        # Patch the `json_argument` method to return the mock_user_ad_data
        with patch.object(SynchronizeAssetsWithAD, "json_argument", return_value=mock_user_ad_data) as mock_json_arg:
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
            create_url = urljoin(base_url + "/", "v2/asset-management/assets")

            # Define how many times each GET request should be expected
            # For each user in the file, the action will:
            # 1. GET asset by name
            # 2. GET assets by detection properties (email and department)
            # Therefore, total GET requests = 2 * number of users
            # Additionally, POST requests to create assets and merge if necessary

            # Mock GET requests for asset name searches (all return no assets)
            def match_asset_name(request):
                search_query = request.qs.get("search", [None])[0]
                also_search = "also_search_in_detection_properties" in request.qs
                return search_query in {"asmith", "bjones"} and not also_search

            requests_mock.get(
                assets_url,
                additional_matcher=match_asset_name,
                json={
                    "total": 0,
                    "items": [],
                },
                status_code=200,
            )

            # Mock GET requests for detection properties (all return no assets)
            def match_detection_properties(request):
                return request.qs.get("also_search_in_detection_properties", [None])[0] == "true"

            requests_mock.get(
                assets_url,
                additional_matcher=match_detection_properties,
                json={
                    "total": 0,
                    "items": [],
                },
                status_code=200,
            )

            # Mock POST requests to create new assets
            # Assuming two assets will be created
            create_responses = [
                {"uuid": "asset-uuid-asmith"},
                {"uuid": "asset-uuid-bjones"},
            ]

            # Use a side effect to return different responses for each POST create
            requests_mock.post(
                create_url,
                json=create_responses.pop(0),
                status_code=200,
            )
            requests_mock.post(
                create_url,
                json=create_responses.pop(0),
                status_code=200,
            )

            # Mock POST requests to merge assets (no sources to merge in this case)
            # Since no existing assets were found, no merge should occur
            # Therefore, no POST merge requests are expected

            # Execute the action
            resp = action_instance.run(arguments_with_file)
            response = resp["data"]

            # Assertions
            assert len(response) == 2, "Expected two response items for two users."
            print(response)
            # Check first user response
            response_item_1 = response[0]
            assert response_item_1["created_asset"] is True, "Asset for asmith should be created."
            assert response_item_1["destination_asset"] in [
                "asset-uuid-asmith",
                "asset-uuid-bjones",
            ], "Destination asset UUID for asmith mismatch."
            assert response_item_1["found_assets"] == [], "Found assets for asmith should be empty."

            # Check second user response
            response_item_2 = response[1]
            assert response_item_2["created_asset"] is True, "Asset for bjones should be created."
            assert response_item_2["destination_asset"] in [
                "asset-uuid-asmith",
                "asset-uuid-bjones",
            ], "Destination asset UUID for bjones mismatch."
            assert response_item_2["found_assets"] == [], "Found assets for bjones should be empty."

            assert (
                len(requests_mock.request_history) == 8
            ), f"Expected 6 HTTP requests, got {len(requests_mock.request_history)}."

            # Verify that `json_argument` was called once with the correct parameters
            mock_json_arg.assert_called_once_with("user_ad_data", arguments_with_file)

            # Verify the payloads of POST create requests
            post_create_requests = [
                req for req in requests_mock.request_history if req.method == "POST" and not req.url.endswith("/merge")
            ]
            assert len(post_create_requests) == 2, "Expected two POST create requests."

            expected_post_create_payloads = [
                {
                    "name": "asmith",
                    "description": "",
                    "type": "account",
                    "category": "user",
                    "reviewed": True,
                    "source": "manual",
                    "props": {"dept": "marketing"},
                    "atoms": {"email": ["asmith@example.com"], "department": ["marketing"]},
                    "community_uuid": "community-1234",
                },
                {
                    "name": "bjones",
                    "description": "",
                    "type": "account",
                    "category": "user",
                    "reviewed": True,
                    "source": "manual",
                    "props": {"dept": "sales"},
                    "atoms": {"email": ["bjones@example.com"], "department": ["sales"]},
                    "community_uuid": "community-1234",
                },
            ]

            for req, expected_payload in zip(post_create_requests, expected_post_create_payloads):
                assert (
                    req.json() == expected_payload
                ), f"POST create request payload mismatch for {expected_payload['name']}."
