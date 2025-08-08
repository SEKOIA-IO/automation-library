from trendmicro_visionone_modules import TrendMicroVisionOneModule
from trendmicro_visionone_modules.action_vision_one_add_alert_note import AddAlertNoteAction
from trendmicro_visionone_modules.action_vision_one_collect_file import CollectFileAction
from trendmicro_visionone_modules.action_vision_one_deisolate_machine import DeIsolateMachineAction
from trendmicro_visionone_modules.action_vision_one_isolate_machine import IsolateMachineAction
from trendmicro_visionone_modules.action_vision_one_scan_machine import ScanMachineAction
from trendmicro_visionone_modules.action_vision_one_terminate_process import TerminateProcessAction
from trendmicro_visionone_modules.action_vision_one_update_alert import UpdateAlertAction

if __name__ == "__main__":
    module = TrendMicroVisionOneModule()
    module.register(AddAlertNoteAction, "action_add_alert_note")
    module.register(CollectFileAction, "action_collect_file")
    module.register(DeIsolateMachineAction, "action_deisolate_machine")
    module.register(IsolateMachineAction, "action_isolate_machine")
    module.register(ScanMachineAction, "action_scan_machine")
    module.register(TerminateProcessAction, "action_terminate_process")
    module.register(UpdateAlertAction, "action_update_alert")
    module.run()
