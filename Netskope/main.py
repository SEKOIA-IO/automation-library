from netskope_modules import NetskopeModule
from netskope_modules.actions.action_append_to_blocklist import AppendToBlocklistAction
from netskope_modules.actions.action_deploy_url_policy import DeployUrlPolicyAction
from netskope_modules.actions.action_get_blocklist import GetBlocklistAction
from netskope_modules.actions.action_quarantine_file import QuarantineFileAction
from netskope_modules.actions.action_remove_from_blocklist import (
    RemoveFromBlocklistAction,
)
from netskope_modules.actions.action_restrict_file_shares import (
    RestrictFileSharesAction,
)
from netskope_modules.actions.action_restrict_user_to_group import (
    RestrictUserToGroupAction,
)
from netskope_modules.actions.action_revoke_user_sessions import (
    RevokeUserSessionsAction,
)
from netskope_modules.actions.action_replace_blocklist import ReplaceBlocklistAction
from netskope_modules.actions.action_update_dlp_incident_status import (
    UpdateDlpIncidentStatusAction,
)
from netskope_modules.connectors.connector_pubsub_lite import PubSubLite
from netskope_modules.connectors.connector_pull_events_v2 import NetskopeEventConnector

if __name__ == "__main__":
    module = NetskopeModule()
    module.register(NetskopeEventConnector, "netskope_events_connector_v2")
    module.register(PubSubLite, "netskope_pubsub_lite")
    module.register(AppendToBlocklistAction, "append_to_blocklist")
    module.register(DeployUrlPolicyAction, "deploy_url_policy")
    module.register(GetBlocklistAction, "get_blocklist")
    module.register(QuarantineFileAction, "quarantine_file")
    module.register(RemoveFromBlocklistAction, "remove_from_blocklist")
    module.register(RestrictFileSharesAction, "restrict_file_shares")
    module.register(RestrictUserToGroupAction, "restrict_user_to_group")
    module.register(RevokeUserSessionsAction, "revoke_user_sessions")
    module.register(ReplaceBlocklistAction, "replace_blocklist")
    module.register(UpdateDlpIncidentStatusAction, "update_dlp_incident_status")
    module.run()
