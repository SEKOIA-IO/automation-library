from cybereason_modules import CybereasonModule
from cybereason_modules.connector_pull_events import CybereasonEventConnector
from cybereason_modules.connector_pull_events_new import CybereasonEventConnectorNew

if __name__ == "__main__":
    module = CybereasonModule()
    module.register(CybereasonEventConnector, "cybereason_events_connector")
    module.register(CybereasonEventConnectorNew, "cybereason_events_connector_new")
    module.run()
