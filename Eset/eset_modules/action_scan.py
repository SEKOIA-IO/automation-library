from typing import Any, Literal

from .action_base import EsetBaseAction


class EsetScanAction(EsetBaseAction):
    def run(self, arguments: Any) -> Any:
        device_uuids: list[str] = arguments["device_uuids"]
        task_expire_time: int = arguments["task_expire_time"]
        scan_profile: Literal["InDepth", "Smart", "ContextMenu", "MyProfile", "Custom"] = arguments["scan_profile"]

        display_name: str | None = arguments.get("display_name", "ScanAll")
        description: str | None = arguments.get("description", "OnDemandScanASAP")
        cleaning_enabled: bool = arguments.get("cleaning_enabled", False)
        shutdown_enabled: bool = arguments.get("shutdown_enabled", False)

        url = f"https://{self.module.configuration.region}.automation.eset.systems/v1/device_tasks"

        payload = {
            "task": {
                "targets": {"devicesUuids": device_uuids},
                "action": {
                    "name": "OnDemandScan",
                    "params": {
                        "@type": "type.googleapis.com/Era.Common.DataDefinition.Task.ESS.OnDemandScan",
                        "cleaningEnabled": cleaning_enabled,
                        "scanProfile": scan_profile,
                        "shutdownEnabled": shutdown_enabled,
                    },
                },
                "description": description,
                "displayName": display_name,
                "triggers": [{"manual": {"expireTime": self.get_expire_time(task_expire_time)}}],
            }
        }
        return self.client.post(url, json=payload, timeout=60)
