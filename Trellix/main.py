"""Entry point for the Trellix connector."""
from logger.config import init_logging
from trellix.connector import TrellixEdrConnector, TrellixModule

if __name__ == "__main__":
    init_logging()
    module = TrellixModule()
    module.register(TrellixEdrConnector, "trellix_edr")
    module.run()
