"""Entry point for the Cato Network connector."""

from cato.connector import CatoModule, CatoSaseConnector

if __name__ == "__main__":
    module = CatoModule()
    module.register(CatoSaseConnector, "cato_sase")
    module.run()
