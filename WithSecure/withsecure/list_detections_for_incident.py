from typing import Any, List

from pydantic import BaseModel

from withsecure.incident_operation_action import IncidentOperationAction


class ActionArguments(BaseModel):
    target: str


class Detection(BaseModel):
    detectionId: str
    incidentId: str
    detectionClass: str
    severity: str
    riskLevel: str
    createdTimestamp: str
    initialReceivedTimestamp: str
    privileges: str | None = None
    exePath: str | None = None
    description: str | None = None
    pid: int | None = None
    exeHash: str | None = None
    deviceId: str | None = None
    activityContext: list[Any] | None = None
    exeName: str | None = None
    name: str | None = None
    cmdl: str | None = None
    username: str | None = None


class DetectionItems(BaseModel):
    detections: List[Detection] = []


class ListDetectionForIncident(IncidentOperationAction):
    results_model = DetectionItems

    def run(self, arguments: ActionArguments) -> DetectionItems:
        # execute the operation
        detections = self._execute_operation_on_incident(
            operation_name="ListDetectionForIncident", target=arguments.target
        )
        return DetectionItems(detections=detections)
