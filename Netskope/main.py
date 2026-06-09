from netskope_modules import NetskopeModule
from netskope_modules.connectors.connector_pubsub_lite import PubSubLite
from netskope_modules.connectors.connector_pull_events_v2 import NetskopeEventConnector
from netskope_modules.actions.action_append_to_blocklist import AppendToBlocklistAction
from netskope_modules.actions.action_get_blocklist import GetBlocklistAction
from netskope_modules.actions.action_remove_from_blocklist import RemoveFromBlocklistAction
from netskope_modules.actions.action_replace_blocklist import ReplaceBlocklistAction
from netskope_modules.connectors.connector_pubsub_lite import PubSubLite
from netskope_modules.connectors.connector_pull_events_v2 import NetskopeEventConnector
from netskope_modules.connectors.connector_security_check import NetskopeSecurityCheckConnector


if __name__ == "__main__":
    module = NetskopeModule()
    module.register(NetskopeEventConnector, "netskope_events_connector_v2")
    module.register(PubSubLite, "netskope_pubsub_lite")
    module.register(AppendToBlocklistAction, "append_to_blocklist")
    module.register(GetBlocklistAction, "get_blocklist")
    module.register(RemoveFromBlocklistAction, "remove_from_blocklist")
    module.register(ReplaceBlocklistAction, "replace_blocklist")
    module.run()
