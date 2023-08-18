"""Entry point for the Cato Network connector."""

from cato.cato_sase_connector import CatoModule, CatoSaseConnector

if __name__ == "__main__":
    module = CatoModule()
    module.register(CatoSaseConnector, "cato_sase")
    module.run()
