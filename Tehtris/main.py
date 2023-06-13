from tehtris_modules import TehtrisModule
from tehtris_modules.trigger_tehtris_events import TehtrisEventConnector

if __name__ == "__main__":
    module = TehtrisModule()
    module.register(TehtrisEventConnector, "tehtris_events_trigger")
    module.run()
