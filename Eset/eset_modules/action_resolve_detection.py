from typing import Any

from .action_base import EsetBaseAction


class EsetResolveDetectionAction(EsetBaseAction):
    def run(self, arguments: Any) -> Any:
        detection_uuid: list[str] = arguments["detection_uuid"]
        comment: str = arguments["comment"]

        url = (
            f"https://{self.module.configuration.region}.incident-management.eset.systems"
            f"/v2/detections/{detection_uuid}:resolve"
        )

        payload = {"note": comment}
        return self.client.post(url, json=payload, timeout=60)
