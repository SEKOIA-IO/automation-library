from anozrway_modules import AnozrwayModule
from anozrway_modules.historical_connector import AnozrwayHistoricalConnector

if __name__ == "__main__":
    module = AnozrwayModule()
    module.register(AnozrwayHistoricalConnector, "anozrway_historical")
    module.run()
