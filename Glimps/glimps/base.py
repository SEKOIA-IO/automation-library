from sekoia_automation.action import Action
from gdetect import Client, GDetectError
from functools import cached_property
from glimps.models import GLIMPSModule


class GLIMPSAction(Action):
    module: GLIMPSModule

    @cached_property
    def gdetect_client(self):
        return Client(self.module.configuration.base_url, self.module.configuration.api_key)

    def _get_token_view_url(self, analysis: dict) -> str:
        """Extract url token view from analysis response, if possible"""
        response = ""
        try:
            response = self.gdetect_client.extract_url_token_view(analysis)
        except GDetectError:
            try:
                response = self.gdetect_client.extract_expert_url(analysis)
            except GDetectError:
                pass
        return response
