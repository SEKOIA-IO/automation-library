"""Entry point for connectors."""

from sekoia_automation.loguru.config import init_logging

from delinea import DelineaModule
from delinea.delinea_pra import DelineaPraConnector

if __name__ == "__main__":
    init_logging()

    module = DelineaModule()
    module.register(DelineaPraConnector, "delinea_pra")
    module.run()
