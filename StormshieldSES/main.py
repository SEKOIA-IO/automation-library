from sekoia_automation.module import Module

from stormshield_module.endpoint_actions import EndpointAgentIsolationAction, EndpointAgentDeisolationAction
from stormshield_module.process_actions import TerminateProcessAction
from stormshield_module.quarantined_file_actions import QuarantineFileAction, RestoreQuarantinedFileAction
from stormshield_module.wait_task import WaitForTaskCompletionAction

if __name__ == "__main__":
    module = Module()
    module.register(EndpointAgentIsolationAction, "stormshield_endpoint_agent_isolation")
    module.register(EndpointAgentDeisolationAction, "stormshield_endpoint_agent_deisolation")
    module.register(TerminateProcessAction, "stormshield_terminate_process")
    module.register(QuarantineFileAction, "stormshield_quarantine_file")
    module.register(RestoreQuarantinedFileAction, "stormshield_restore_quarantined_file")
    module.register(WaitForTaskCompletionAction, "stormshield_wait_for_task_completion")
    module.run()
