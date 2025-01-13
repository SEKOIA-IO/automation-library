from typing import Any

from .action_base import EsetBaseAction


class EsetIsolateEndpointAction(EsetBaseAction):
    def run(self, arguments: Any) -> Any:
        device_uuids: list[str] = arguments["device_uuids"]
        task_expire_time: int = arguments["task_expire_time"]
        display_name: str | None = arguments.get("display_name", "IsolateDevice")
        description: str | None = arguments.get("description", "IsolateDeviceASAP")

        url = f"https://{self.module.configuration.region}.automation.eset.systems/v1/device_tasks"

        payload = {
            "task": {
                "action": {"name": "StartNetworkIsolation"},
                "description": description,
                "displayName": display_name,
                "triggers": [{"manual": {"expireTime": self.get_expire_time(task_expire_time)}}],
                "targets": {"devicesUuids": device_uuids},
            }
        }
        return self.client.post(url, json=payload, timeout=60)
