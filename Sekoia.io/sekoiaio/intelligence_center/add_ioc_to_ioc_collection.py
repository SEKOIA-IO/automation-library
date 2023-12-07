import requests

from .base import InThreatBaseAction


class AddIOCtoIOCCollectionAction(InThreatBaseAction):
    def run(self, arguments: dict):
        indicators = self.json_argument("indicators", arguments)
        ioc_collection_id = self.json_argument("ioc_collection_id", arguments)
        indicator_type = self.json_argument("indicator_type", arguments)
        data = {"format": indicator_type, "indicators": "\n".join(indicators)}
        result = requests.post(
            self.url("ioc-collections/" + ioc_collection_id + "/indicators/text"), json=data, headers=self.headers
        )

        if not result.ok:
            self.error(
                f"Could not post indicators to IOC Collection: '{result.text}', status code: {result.status_code}"
            )
