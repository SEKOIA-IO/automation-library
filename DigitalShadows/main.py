from sekoia_automation.module import Module

from digitalshadows_modules.trigger_searchlight_events import SearchLightTrigger

if __name__ == "__main__":
    module = Module()
    module.register(SearchLightTrigger, "searchlight_alerts_trigger")
    module.run()
