from azure_monitor_modules import AzureMonitorModule
from azure_monitor_modules.action_query import AzureMonitorQueryAction

if __name__ == "__main__":
    module = AzureMonitorModule()
    module.register(AzureMonitorQueryAction, "action_query_logs")
    module.run()
