from sekoia_automation.module import Module

from anozrway_modules.historical_connector import AnozrwayHistoricalConnector

if __name__ == "__main__":
    module = Module()

    # Connector (intake)
    module.register(AnozrwayHistoricalConnector, "anozrway_historical")

    module.run()
