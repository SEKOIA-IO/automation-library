from secuserve_modules import SecuserveModule
from secuserve_modules.connector_esecuremail_events import ESecuremailEventsConnector

if __name__ == "__main__":
    module = SecuserveModule()
    module.register(ESecuremailEventsConnector, "collect_esecuremail_events")
    module.run()
