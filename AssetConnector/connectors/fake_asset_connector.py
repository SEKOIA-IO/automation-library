import time
import faker
from collections.abc import Generator
from typing import Any

from .models import AssetObject
from .base import AssetConnector


class FakeAssetConnector(AssetConnector):

    def _generate_fake_api_call(self) -> dict[str, Any]:
        """
        Generate a fake API call response with a list of assets.
        This is for testing purposes only.
        Returns:
            dict[str, Any]: A dictionary containing a list of fake assets and their total count.
        """

        fake = faker.Faker()
        api_response = {}
        data = []
        for _ in range(100):
            asset = {
                "name": fake.company(),
                "type": fake.random_element(elements=("host", "account")),
            }
            data.append(asset)
        api_response["data"] = data
        api_response["total"] = len(data)
        return api_response

    def get_assets(self) -> Generator[AssetObject, None, None]:
        """
        Fake implementation of get_assets that returns a static list of assets.
        This is for testing purposes only.
        """

        while self.running:
            api_response = self._generate_fake_api_call()
            for asset in api_response["data"]:
                yield asset

            # Simulate a delay to mimic real-world asset fetching
            time.sleep(3600)  # Sleep for 1 hour
