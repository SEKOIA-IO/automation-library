from typing import Any

from censys.base import CensysIndex
from censys.certificates import CensysCertificates
from censys.ipv4 import CensysIPv4
from censys.websites import CensysWebsites
from sekoia_automation.action import Action


class CensysAction(Action):
    index_classes = {
        "ipv4": CensysIPv4,
        "websites": CensysWebsites,
        "certificates": CensysCertificates,
    }

    @property
    def user_id(self) -> str:
        return self.module.configuration["api_user_id"]

    @property
    def user_secret(self) -> str:
        return self.module.configuration["api_user_secret"]

    def get_index_class(self, index: str) -> CensysIndex:
        return self.index_classes[index](api_id=self.user_id, api_secret=self.user_secret)

    def run(self, arguments: dict):
        index_class = self.get_index_class(arguments["index"])
        result = self.execute_request(index_class, arguments)
        return self.json_result("result", result)

    def execute_request(self, index_class: CensysIndex, arguments: dict) -> Any:
        """
        Execute the request and return any json serializable result
        """
        raise NotImplementedError()
