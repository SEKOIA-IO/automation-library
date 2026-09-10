from thor_cloud_modules import ThorCloudModule

from thor_cloud_modules.connector import ThorCloudConnector

if __name__ == "__main__":
    module = ThorCloudModule()
    module.register(ThorCloudConnector, "ThorCloudConnector")
    module.run()
