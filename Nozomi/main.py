from nozomi_networks import NozomiModule
from nozomi_networks.nozomi_vantage_connector import NozomiVantageConnector

if __name__ == "__main__":
    module = NozomiModule()

    module.register(NozomiVantageConnector, "nozomi_vantage")

    module.run()
