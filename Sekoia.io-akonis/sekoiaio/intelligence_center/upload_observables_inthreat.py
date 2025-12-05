import requests

from .base import InThreatBaseAction


class UploadObservablesAction(InThreatBaseAction):
    def run(self, arguments: dict):
        observables = self.json_argument("observables", arguments)
        data = {"data": observables}
        result = requests.post(self.url("observables/bulk"), json=data, headers=self.headers)

        if not result.ok:
            self.error(f"Could not post observables: '{result.text}', status code: {result.status_code}")
