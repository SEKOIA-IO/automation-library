from thor_cloud_modules import GenerateLauncherAction, ThorCloudModule

from thor_cloud_modules.account_validator import ThorCloudAccountValidator
from thor_cloud_modules.connector import ThorCloudConnector

if __name__ == "__main__":
    module = ThorCloudModule()
    module.register(GenerateLauncherAction, "GenerateLauncherAction")
    module.register(ThorCloudConnector, "ThorCloudConnector")
    module.register_account_validator(ThorCloudAccountValidator)
    module.run()
