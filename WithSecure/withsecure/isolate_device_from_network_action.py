from pydantic import BaseModel

from withsecure.device_operation_action import DeviceOperationAction
from withsecure.models import RemoteOperationResponse


class ActionArguments(BaseModel):
    target: str
    message: str | None = None


class IsolateDeviceFromNetworkAction(DeviceOperationAction):
    results_model = RemoteOperationResponse

    def run(self, arguments: ActionArguments) -> RemoteOperationResponse:
        parameters = {}
        if arguments.message:
            parameters["message"] = arguments.message

        # execute the operation
        response = self._execute_operation_on_device(
            operation_name="isolateFromNetwork", target=arguments.target, parameters=parameters
        )

        return RemoteOperationResponse(
            multistatus=response.get("multistatus", []), transactionId=response["transactionId"]
        )
