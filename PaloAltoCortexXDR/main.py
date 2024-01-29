from cortex_module.base import CortexModule
from cortex_module.cortex_edr_connector import CortexQueryEDRTrigger

if __name__ == "__main__":
    module = CortexModule()
    module.register(CortexQueryEDRTrigger, "cortex_query_alerts")
    module.run()
