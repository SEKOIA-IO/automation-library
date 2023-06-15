from sekoia_automation.module import Module

from azure_module.trigger_azure_eventhub import AzureEventsHubTrigger

if __name__ == "__main__":
    module = Module()
    module.register(AzureEventsHubTrigger, "azure_eventhub_messages_trigger")
    module.run()
