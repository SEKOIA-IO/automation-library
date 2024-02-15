from sekoia_automation.module import Module

from retarus_modules.connector import RetarusConnector

if __name__ == "__main__":
    module = Module()
    module.register(RetarusConnector, "retarus_connector")
    module.run()
