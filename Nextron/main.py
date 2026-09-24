from thor_cloud_modules import GenerateLauncherAction, ThorCloudModule

from thor_cloud_modules.connector import ThorCloudConnector

if __name__ == "__main__":
    module = ThorCloudModule()
    module.register(GenerateLauncherAction, "GenerateLauncherAction")
    module.register(ThorCloudConnector, "ThorCloudConnector")
    module.run()
