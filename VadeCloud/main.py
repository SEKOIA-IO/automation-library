from vadecloud_modules import VadeCloudModule
from vadecloud_modules.trigger_vade_cloud_logs import VadeCloudLogsConnector

if __name__ == "__main__":
    module = VadeCloudModule()
    module.register(VadeCloudLogsConnector, "vade_cloud_connector")
    module.run()
