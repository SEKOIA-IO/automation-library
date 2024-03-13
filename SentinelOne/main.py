from sentinelone_module.agents.isolation import DeisolateEndpointAction, IsolateEndpointAction
from sentinelone_module.base import SentinelOneModule
from sentinelone_module.deep_visibility.consumer import DeepVisibilityTrigger
from sentinelone_module.deep_visibility.query import QueryDeepVisibilityAction
from sentinelone_module.logs.connector import SentinelOneLogsConnector
from sentinelone_module.rso.execute import ExecuteRemoteScriptAction
from sentinelone_module.threats.get_malwares import GetMalwaresAction

if __name__ == "__main__":
    module = SentinelOneModule()
    module.register(IsolateEndpointAction, "sentinelone_agents_endpoint_isolation")
    module.register(DeisolateEndpointAction, "sentinelone_agents_endpoint_deisolation")
    module.register(QueryDeepVisibilityAction, "sentinelone_deep_visibility_query")
    module.register(ExecuteRemoteScriptAction, "sentinelone_rso_execute")
    module.register(GetMalwaresAction, "sentinelone_threat_get_malwares")
    module.register(DeepVisibilityTrigger, "sentinelone_deep_visibility_consumer")
    module.register(SentinelOneLogsConnector, "sentinelone_log_connector")
    module.run()
