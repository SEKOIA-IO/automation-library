from netskope_modules import NetskopeModule
from netskope_modules.connectors.connector_pubsub_lite import PubSubLite
from netskope_modules.connectors.connector_pull_events_v2 import NetskopeEventConnector
from netskope_modules.actions.action_append_to_blocklist import AppendToBlocklistAction
from netskope_modules.actions.action_delete_blocklist import DeleteBlocklistAction
from netskope_modules.actions.action_replace_blocklist import ReplaceBlocklistAction


if __name__ == "__main__":
    module = NetskopeModule()
    module.register(NetskopeEventConnector, "netskope_events_connector_v2")
    module.register(PubSubLite, "netskope_pubsub_lite")
    module.register(AppendToBlocklistAction, "append_to_blocklist")
    module.register(ReplaceBlocklistAction, "replace_blocklist")
    module.register(DeleteBlocklistAction, "delete_blocklist")
    module.run()
