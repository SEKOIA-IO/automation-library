import json
from posixpath import join as urljoin

import requests
from sekoia_automation.action import Action

from sekoiaio.utils import user_agent


class PushEventToIntake(Action):
    def _delete_file(self, arguments: dict):
        event_path = arguments.get("event_path") or arguments.get("events_path")
        if event_path:
            filepath = self._data_path.joinpath(event_path)
            if filepath.is_file():
                filepath.unlink()

    def run(self, arguments) -> dict:
        events = []

        arg_event = self.json_argument("event", arguments, required=False)
        if arg_event:
            if isinstance(arg_event, str):
                events.append(arg_event)
            else:
                events.append(json.dumps(arg_event))

        arg_events = self.json_argument("events", arguments, required=False) or []
        for event in arg_events:
            if isinstance(event, str):
                events.append(event)
            else:
                events.append(json.dumps(event))

        # no event to push
        if not events:
            self.log("No event to push", level="info")
            return {"event_ids": []}

        # pushing the events
        intake_host = arguments.get("intake_server", "https://intake.sekoia.io")
        batch_api = urljoin(intake_host, "batch")
        content = {"intake_key": arguments["intake_key"], "jsons": events}
        res = requests.post(batch_api, json=content, headers={"User-Agent": user_agent()})

        if res.status_code > 299:
            self.log(f"Intake rejected events: {res.text}", level="error")
            res.raise_for_status()

        if not arguments.get("keep_file_after_push", False):
            self._delete_file(arguments)

        return res.json()
