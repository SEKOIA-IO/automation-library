from trendmicro_modules import TrendMicroModule
from trendmicro_modules.action_vision_one_add_alert_note import AddAlertNoteAction
from trendmicro_modules.action_vision_one_collect_file import CollectFileAction
from trendmicro_modules.action_vision_one_deisolate_machine import DeIsolateMachineAction
from trendmicro_modules.action_vision_one_isolate_machine import IsolateMachineAction
from trendmicro_modules.action_vision_one_scan_machine import ScanMachineAction
from trendmicro_modules.action_vision_one_terminate_process import TerminateProcessAction
from trendmicro_modules.action_vision_one_update_alert import UpdateAlertAction
from trendmicro_modules.trigger_email_sec import TrendMicroEmailSecurityConnector
from trendmicro_modules.trigger_vision_one_oat import TrendMicroVisionOneOATConnector
from trendmicro_modules.trigger_vision_one_workbench import TrendMicroVisionOneWorkbenchConnector

if __name__ == "__main__":
    module = TrendMicroModule()
    module.register(TrendMicroEmailSecurityConnector, "trend_micro_email_security")
    module.register(TrendMicroVisionOneWorkbenchConnector, "trend_micro_vision_one_workbench")
    module.register(TrendMicroVisionOneOATConnector, "trend_micro_vision_one_oat")

    module.register(CollectFileAction, "action_collect_file")
    module.register(ScanMachineAction, "action_scan_machine")
    module.register(TerminateProcessAction, "action_terminate_process")
    module.register(IsolateMachineAction, "action_isolate_machine")
    module.register(AddAlertNoteAction, "action_add_alert_note")
    module.register(UpdateAlertAction, "action_update_alert")
    module.register(DeIsolateMachineAction, "action_deisolate_machine")
    module.run()
