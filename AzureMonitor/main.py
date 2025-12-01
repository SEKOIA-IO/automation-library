from azure_monitor_modules import AzureMonitorModule
from azure_monitor_modules.action_query import AzureMonitorQueryAction
from azure_monitor_modules.azure_activity_logs import AzureActivityLogsConnector

if __name__ == "__main__":
    module = AzureMonitorModule()
    module.register(AzureMonitorQueryAction, "action_query_logs")
    module.register(AzureActivityLogsConnector, "azure_activity_logs")
    module.run()
