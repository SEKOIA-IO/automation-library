from netskope_modules import NetskopeModule
from netskope_modules.connector_pubsub_lite import PubSubLite
from netskope_modules.connector_pull_events_v2 import NetskopeEventConnector
from netskope_modules.actions.append_to_blocklist import AppendToBlocklistAction
from netskope_modules.actions.replace_blocklist import ReplaceBlocklistAction


if __name__ == "__main__":
    module = NetskopeModule()

    module.register(NetskopeEventConnector, "netskope_events_connector_v2")
    module.register(PubSubLite, "netskope_pubsub_lite")
    module.register(AppendToBlocklistAction, "append_to_blocklist")
    module.register(ReplaceBlocklistAction, "replace_blocklist")
    module.run()
