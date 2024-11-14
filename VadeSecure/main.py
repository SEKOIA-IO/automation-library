from vadesecure_modules import VadeSecureModule
from vadesecure_modules.connector_m365_events import M365EventsConnector
from vadesecure_modules.trigger_m365_events import M365EventsTrigger

if __name__ == "__main__":
    module = VadeSecureModule()
    module.register(M365EventsTrigger, "m365_events_trigger")
    module.register(M365EventsConnector, "m365_events_connector")
    module.run()
