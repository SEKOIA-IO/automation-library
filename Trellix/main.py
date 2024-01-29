"""Entry point for the Trellix connector."""

from sekoia_automation.loguru.config import init_logging

from connectors import TrellixModule
from connectors.trellix_edr_connector import TrellixEdrConnector
from connectors.trellix_epo_connector import TrellixEpoConnector

if __name__ == "__main__":
    init_logging()
    module = TrellixModule()

    module.register(TrellixEpoConnector, "trellix_epo")
    module.register(TrellixEdrConnector, "trellix_edr")

    module.run()
