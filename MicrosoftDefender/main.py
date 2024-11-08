from microsoftdefender_modules import MicrosoftDefenderModule
from microsoftdefender_modules.action_cancel_machine_action import CancelMachineAction
from microsoftdefender_modules.action_get_machine_action import GetMachineAction
from microsoftdefender_modules.action_isolate_machine import IsolateMachineAction
from microsoftdefender_modules.action_push_indicators import PushIndicatorsAction
from microsoftdefender_modules.action_restrict_code_execution import RestrictCodeExecutionAction
from microsoftdefender_modules.action_scan_machine import ScanMachineAction
from microsoftdefender_modules.action_unisolate_machine import UnIsolateMachineAction
from microsoftdefender_modules.action_unrestrict_code_execution import UnRestrictCodeExecutionAction
from microsoftdefender_modules.action_update_alert import UpdateAlertAction

if __name__ == "__main__":
    module = MicrosoftDefenderModule()
    module.register(UpdateAlertAction, "UpdateAlertAction")
    module.register(UpdateAlertAction, "AddCommentToAlert")
    module.register(GetMachineAction, "GetMachineAction")
    module.register(ScanMachineAction, "ScanMachineAction")
    module.register(PushIndicatorsAction, "PushIndicatorsAction")
    module.register(UnRestrictCodeExecutionAction, "UnRestrictCodeExecutionAction")
    module.register(RestrictCodeExecutionAction, "RestrictCodeExecutionAction")
    module.register(UnIsolateMachineAction, "UnIsolateMachineAction")
    module.register(IsolateMachineAction, "IsolateMachineAction")
    module.register(CancelMachineAction, "CancelMachineAction")
    module.run()
