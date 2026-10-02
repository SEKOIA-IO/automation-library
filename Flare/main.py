from flareio_modules import FlareIOModule
from flareio_modules.account_validator import FlareAccountValidator
from flareio_modules.trigger_flare_events import FlareEventsConnector

if __name__ == "__main__":
    module = FlareIOModule()
    module.register_account_validator(FlareAccountValidator)
    module.register(FlareEventsConnector, "flare_events_trigger")
    module.run()
