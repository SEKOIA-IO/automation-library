from pydantic import BaseModel

from withsecure.device_operation_action import DeviceOperationAction


class ActionArguments(BaseModel):
    target: str


class ReleaseDeviceFromNetworkIsolationAction(DeviceOperationAction):
    def run(self, arguments: ActionArguments) -> None:
        # execute the operation
        self._execute_operation_on_device(operation_name="releaseFromNetworkIsolation", target=arguments.target)
