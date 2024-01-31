from unittest.mock import Mock, patch
import pytest
import requests

from sekoiaio.triggers.intelligence import IOCCollectionTrigger


class TestIOCCollectionTrigger:
    @pytest.fixture
    def trigger_instance(self, data_storage):
        # You may need to mock/stub certain dependencies or provide necessary configurations here
        return IOCCollectionTrigger(data_path=data_storage)

    @patch("requests.get")
    def test_fetch_objects_success(self, mock_get, trigger_instance):
        # Mock the response from the API
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"has_more": False, "items": [{"sample_key": "sample_value"}]}
        mock_get.return_value = mock_response

        # Mock necessary configurations
        trigger_instance.module.configuration = {
            "base_url": "https://example.com",
            "api_key": "your_api_key",
        }
        trigger_instance.configuration = {"ioc_collection_id": "your_ioc_collection_id"}

        # Call the method to test
        objects = trigger_instance.fetch_objects()

        # Assertions
        assert objects == [{"sample_key": "sample_value"}]
