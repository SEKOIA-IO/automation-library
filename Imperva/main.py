from imperva import ImpervaModule
from imperva.fetch_logs_v2 import ImpervaLogsConnector

if __name__ == "__main__":
    module = ImpervaModule()
    module.register(ImpervaLogsConnector, name="imperva_logs")
    module.run()
