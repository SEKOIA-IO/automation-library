from pydantic import BaseModel

from withsecure.device_operation_action import DeviceOperationAction


class ActionArguments(BaseModel):
    target: str
    message: str | None = None


class RemoteOperationResponse(BaseModel):
    multistatus: list
    transactionId: str


class IsolateDeviceFromNetworkAction(DeviceOperationAction):
    def run(self, arguments: ActionArguments) -> None:
        parameters = {}
        if arguments.message:
            parameters["message"] = arguments.message

        # execute the operation
        response = self._execute_operation_on_device(
            operation_name="isolateFromNetwork", target=arguments.target, parameters=parameters
        )

        return RemoteOperationResponse(
            multistatus=response.get("multistatus"), transactionId=response.get("transactionId")
        )
