from sentinelone_module.agents.init_scan import InitiateScanAction
from sentinelone_module.agents.isolation import DeisolateEndpointAction, IsolateEndpointAction
from sentinelone_module.base import SentinelOneModule
from sentinelone_module.deep_visibility.consumer import DeepVisibilityTrigger
from sentinelone_module.deep_visibility.query import QueryDeepVisibilityAction
from sentinelone_module.iocs.create_iocs import CreateIOCsAction
from sentinelone_module.logs.connector import SentinelOneLogsConnector
from sentinelone_module.rso.execute import ExecuteRemoteScriptAction
from sentinelone_module.singularity.connectors import SingularityIdentityConnector
from sentinelone_module.threats.create_threat_note import CreateThreatNoteAction
from sentinelone_module.threats.get_malwares import GetMalwaresAction
from sentinelone_module.threats.update_threat_incident import UpdateThreatIncidentAction

if __name__ == "__main__":
    module = SentinelOneModule()
    module.register(IsolateEndpointAction, "sentinelone_agents_endpoint_isolation")
    module.register(DeisolateEndpointAction, "sentinelone_agents_endpoint_deisolation")
    module.register(QueryDeepVisibilityAction, "sentinelone_deep_visibility_query")
    module.register(ExecuteRemoteScriptAction, "sentinelone_rso_execute")
    module.register(GetMalwaresAction, "sentinelone_threat_get_malwares")
    module.register(InitiateScanAction, "sentinelone_agents_init_scan")
    module.register(CreateIOCsAction, "sentinelone_iocs_create_iocs")
    module.register(CreateThreatNoteAction, "sentinelone_threat_create_threat_note")
    module.register(UpdateThreatIncidentAction, "sentinelone_threat_update_incident")
    module.register(DeepVisibilityTrigger, "sentinelone_deep_visibility_consumer")
    module.register(SentinelOneLogsConnector, "sentinelone_log_connector")
    module.register(SingularityIdentityConnector, "sentinelone_identity_connector")
    module.run()
