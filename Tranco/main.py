from sekoia_automation.module import Module

from tranco_module.triggers import FetchTrancoListTrigger

if __name__ == "__main__":
    module = Module()
    module.register(FetchTrancoListTrigger, "fetch_tranco_list")
    module.run()
