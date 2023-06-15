from sekoia_automation.module import Module

from service_now import GetTable

if __name__ == "__main__":
    module = Module()
    module.register(GetTable, "servicenow_get_table")
    module.run()
