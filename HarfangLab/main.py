from sekoia_automation.module import Module

from harfanglab.download_file_from_endpoint import DownloadFileFromEndpointAction
from harfanglab.endpoint_actions import (
    EndpointAgentDeisolationAction,
    EndpointAgentIsolationAction,
    EndpointGroupDeisolationAction,
    EndpointGroupIsolationAction,
)
from harfanglab.get_hostnames_by_ip_action import GetHostnamesByIP
from harfanglab.get_pipe_list_action import GetPipeListAction
from harfanglab.get_process_list_action import GetProcessListAction
from harfanglab.iocs import CreateIOCs
from harfanglab.threat_actions import AddCommentToThreat, UpdateThreatStatus

if __name__ == "__main__":
    module = Module()
    module.register(GetProcessListAction, "harfanglab_get_process_list")
    module.register(GetPipeListAction, "harfanglab_get_pipe_list")
    module.register(EndpointGroupIsolationAction, "harfanglab_endpoint_group_isolation")
    module.register(EndpointGroupDeisolationAction, "harfanglab_endpoint_group_deisolation")
    module.register(EndpointAgentIsolationAction, "harfanglab_endpoint_agent_isolation")
    module.register(EndpointAgentDeisolationAction, "harfanglab_endpoint_agent_deisolation")
    module.register(GetHostnamesByIP, "harfanglab_get_hostnames_by_ip")
    module.register(DownloadFileFromEndpointAction, "harfanglab_download_file_from_endpoint")
    module.register(UpdateThreatStatus, "harfanglab_update_threat_status")
    module.register(AddCommentToThreat, "harfanglab_add_comment_to_threat")
    module.register(CreateIOCs, "harfanglab_create_iocs")
    module.run()
