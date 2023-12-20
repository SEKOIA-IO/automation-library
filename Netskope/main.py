from netskope_modules import NetskopeModule
from netskope_modules.connector_pull_events_v2 import NetskopeEventConnector
from netskope_modules.connector_pubsub_lite import PubSubLite


if __name__ == "__main__":
    module = NetskopeModule()
    module.register(NetskopeEventConnector, "netskope_events_connector_v2")
    module.register(PubSubLite, "netskope_pubsub_lite")
    module.run()
