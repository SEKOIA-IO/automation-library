from sekoia_automation.module import Module

from ipinfo.trigger_fetch_ipinfo_database import TriggerFetchIPInfoDatabase

if __name__ == "__main__":
    module = Module()
    module.register(TriggerFetchIPInfoDatabase, "fetch_ipinfo_database")
    module.run()
