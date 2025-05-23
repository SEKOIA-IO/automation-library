from cortex_module.actions.action_block_malicious_files import BlockMaliciousFilesAction
from cortex_module.actions.action_comment_alert import CommentAlertAction
from cortex_module.actions.action_isolate import IsolateAction, UnisolateAction
from cortex_module.actions.action_quarantine import QuarantineAction
from cortex_module.actions.action_update_alert import UpdateAlertAction
from cortex_module.actions.action_xql_query import XQLQueryAction
from cortex_module.base import CortexModule
from cortex_module.cortex_edr_connector import CortexQueryEDRTrigger

if __name__ == "__main__":
    module = CortexModule()
    module.register(CortexQueryEDRTrigger, "cortex_query_alerts")

    module.register(QuarantineAction, "quarantine_file")
    module.register(IsolateAction, "isolate_endpoint")
    module.register(UnisolateAction, "unisolate_endpoint")
    module.register(UpdateAlertAction, "update_alert_status_severity")
    module.register(CommentAlertAction, "comment_alert")
    module.register(BlockMaliciousFilesAction, "block_malicious_files")
    module.register(XQLQueryAction, "xql_query")

    module.run()
