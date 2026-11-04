from cortex_module.base import CortexModule
from cortex_module.cortex_xdr_issues_connector import CortexQueryXDRIssuesTrigger

if __name__ == "__main__":
    module = CortexModule()
    module.register(CortexQueryXDRIssuesTrigger, "cortex_query_issues")

    module.run()
