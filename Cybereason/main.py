from cybereason_modules import CybereasonModule
from cybereason_modules.connector_pull_events import CybereasonEventConnector

if __name__ == "__main__":
    module = CybereasonModule()
    module.register(CybereasonEventConnector, "cybereason_events_connector")
    module.run()
