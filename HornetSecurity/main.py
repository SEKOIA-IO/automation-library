from hornetsecurity_modules import HornetsecurityModule

from hornetsecurity_modules.connector_smp_events import SMPEventsConnector

if __name__ == "__main__":
    module = HornetsecurityModule()
    module.register(SMPEventsConnector, "collect_smp_events")
    module.run()
