from sekoia_automation.action import Action
from gdetect import Client
from functools import cached_property
from glimps.models import GlimpsModule


class GlimpsAction(Action):
    module: GlimpsModule

    @cached_property
    def gdetect_client(self):
        return Client(
            self.module.configuration.base_url, self.module.configuration.api_key
        )
