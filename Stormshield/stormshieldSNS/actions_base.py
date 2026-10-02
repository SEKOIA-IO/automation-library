from functools import cached_property

from sekoia_automation.action import Action

from stormshieldSNS.client.sns_client import StormshieldSNSClient
from stormshieldSNS.models.common_models import StormshieldSNSModule


class StormshieldSNSAction(Action):
    module: StormshieldSNSModule

    @cached_property
    def client(self) -> StormshieldSNSClient:
        return StormshieldSNSClient(
            base_url=self.module.configuration.url,
            api_token=self.module.configuration.api_token,
        )
