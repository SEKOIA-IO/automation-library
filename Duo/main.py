from duo import DuoModule
from duo.connector import DuoAdminLogsConnector

if __name__ == "__main__":
    module = DuoModule()
    module.register(DuoAdminLogsConnector, "duo_admin_logs")
    module.run()
