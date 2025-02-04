from microsoft_sentinel import MicrosoftSentinelModule
from microsoft_sentinel.connector_microsoft_sentinel import MicrosoftSentineldConnector

if __name__ == "__main__":
    module = MicrosoftSentinelModule()
    module.register(MicrosoftSentineldConnector, "get_microsoft_sentinel_alerts")
    module.run()
