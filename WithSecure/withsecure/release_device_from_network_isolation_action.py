from pydantic import BaseModel
from withsecure.models import RemoteOperationResponse

from withsecure.device_operation_action import DeviceOperationAction


class ActionArguments(BaseModel):
    target: str


class ReleaseDeviceFromNetworkIsolationAction(DeviceOperationAction):
    def run(self, arguments: ActionArguments) -> RemoteOperationResponse:
        # execute the operation
        response = self._execute_operation_on_device(
            operation_name="releaseFromNetworkIsolation", target=arguments.target
        )

        return RemoteOperationResponse(
            multistatus=response.get("multistatus", []), transactionId=response["transactionId"]
        )
