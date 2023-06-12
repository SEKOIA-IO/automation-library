from sekoia_automation.module import Module

from thehive.create_alert import TheHiveCreateAlert

if __name__ == "__main__":
    module = Module()

    module.register(TheHiveCreateAlert, "thehive_create_alert")

    module.run()
