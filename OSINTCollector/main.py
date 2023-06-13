from osintcollector.trigger_osint import OSINTTrigger
from sekoia_automation.module import Module

if __name__ == "__main__":
    module = Module()

    module.register(OSINTTrigger, "osint_trigger")
    module.run()
