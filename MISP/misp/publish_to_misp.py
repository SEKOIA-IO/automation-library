import json
from typing import Any
from uuid import uuid4

from pymisp import MISPEvent, PyMISP
from sekoia_automation.action import Action


class PublishToMISPAction(Action):
    @property
    def url(self):
        return self.module.configuration["misp_url"]

    @property
    def api_key(self):
        return (self.module.configuration["misp_api_key"],)

    def run(self, arguments):
        event = self.json_argument("event", arguments)
        api = PyMISP(url=self.url, key=self.api_key, ssl=True)
        created_event = api.add_event(event)
        return self.json_result("event", created_event)

    def json_result(self, name: str, value: Any) -> dict:
        """Create a result dict with a direct value or inside a file.

        Creates a file by default.
        If the last `json_argument` was resolved using a direct value, it returns a direct value instead.
        """
        if name != "event" or not isinstance(value, MISPEvent):
            return super().json_result(name, value)

        value = value.to_json()
        if self._result_as_file:
            filename = f"{name}-{uuid4()}.json"
            with self._data_path.joinpath(filename).open("w") as f:
                f.write(value)
            return {"event_path": filename}
        else:
            # `to_dict` method is not converting the objects recursively.
            # To get a dict with only primitive types we convert it to json and then load it.
            return {"event": json.loads(value)}
