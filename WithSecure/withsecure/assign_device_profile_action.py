from pydantic import BaseModel

from withsecure.device_operation_action import DeviceOperationAction


class ActionArguments(BaseModel):
    target: str
    profile: str 


class AssignDeviceProfileAction(DeviceOperationAction):
    def run(self, arguments: ActionArguments):
        parameters["profile"] = arguments.profile


        # execute the operation
        self._execute_operation_on_device(
            operation_name="assignProfile", target=arguments.target, parameters=arguments.profile
