from sekoia_automation.module import Module

from rss.trigger_rss import RSSTrigger

if __name__ == "__main__":
    module = Module()

    module.register(RSSTrigger, "rss_trigger")

    module.run()
