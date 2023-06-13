from sekoia_automation.module import Module

from iptoasn.trigger_fetch_iptoasn_database import TriggerFetchIPtoASNDatabase

if __name__ == "__main__":
    module = Module()
    module.register(TriggerFetchIPtoASNDatabase, "fetch_iptoasn_database")
    module.run()
