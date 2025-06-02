import time
import faker
from typing import Any
from collections.abc import Generator
from pydantic import BaseModel, Field

from sekoia_automation.module import Module

from .models import AssetObject
from .base import AssetConnector


class FakeAssetConnectorModuleConfiguration(BaseModel):
    len_data_to_send: int = Field(..., description="Number of assets to send in each batch", ge=1)
    time_sleep: int = Field(..., description="Time to sleep between asset fetches in seconds", ge=0)


class FakeAssetConnectorModule(Module):
    configuration: FakeAssetConnectorModuleConfiguration


class FakeAssetConnector(AssetConnector):
    module: FakeAssetConnectorModule

    def _generate_fake_api_call(self) -> dict[str, Any]:
        """
        Generate a fake API call response with a list of assets.
        This is for testing purposes only.
        Returns:
            dict[str, Any]: A dictionary containing a list of fake assets and their total count.
        """

        fake = faker.Faker()
        api_response: dict[str, Any] = {}
        data = []
        for _ in range(self.module.configuration.len_data_to_send):
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

            yield from map(AssetObject.model_validate, api_response["data"])

            # Simulate a delay to mimic real-world asset fetching
            time.sleep(self.module.configuration.time_sleep)
