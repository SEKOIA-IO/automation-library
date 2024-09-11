from pydantic import BaseModel

from withsecure.device_operation_action import DeviceOperationAction
from withsecure.models import RemoteOperationResponse


class ActionArguments(BaseModel):
    target: str


class ReleaseDeviceFromNetworkIsolationAction(DeviceOperationAction):
    results_model = RemoteOperationResponse

    def run(self, arguments: ActionArguments) -> RemoteOperationResponse:
        # execute the operation
        response = self._execute_operation_on_device(
            operation_name="releaseFromNetworkIsolation", target=arguments.target
        )

        return RemoteOperationResponse(
            multistatus=response.get("multistatus", []), transactionId=response["transactionId"]
        )
