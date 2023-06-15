from pydantic import BaseModel

from withsecure.device_operation_action import DeviceOperationAction


class ActionArguments(BaseModel):
    target: str
    message: str | None = None


class IsolateDeviceFromNetworkAction(DeviceOperationAction):
    def run(self, arguments: ActionArguments):
        parameters = {}
        if arguments.message:
            parameters["message"] = arguments.message

        # execute the operation
        self._execute_operation_on_device(
            operation_name="isolateFromNetwork", target=arguments.target, parameters=parameters
        )
