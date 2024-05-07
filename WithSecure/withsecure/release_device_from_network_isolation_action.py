from pydantic import BaseModel

from withsecure.device_operation_action import DeviceOperationAction


class ActionArguments(BaseModel):
    target: str


class RemoteOperationResponse(BaseModel):
    multistatus: list
    transactionId: str


class ReleaseDeviceFromNetworkIsolationAction(DeviceOperationAction):
    def run(self, arguments: ActionArguments) -> None:
        # execute the operation
        response = self._execute_operation_on_device(
            operation_name="releaseFromNetworkIsolation", target=arguments.target
        )

        return RemoteOperationResponse(
            multistatus=response.get("multistatus"), transactionId=response.get("transactionId")
        )
