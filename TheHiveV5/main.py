from sekoia_automation.module import Module

from thehive.create_alert import TheHiveCreateAlertV5

if __name__ == "__main__":
    module = Module()

    module.register(TheHiveCreateAlertV5, "thehive_create_alert")

    module.run()
