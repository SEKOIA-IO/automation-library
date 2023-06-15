from jumpcloud_modules import JumpcloudDirectoryInsightsModule

from jumpcloud_modules.jumpcloud_pull_events import JumpcloudDirectoryInsightsConnector


if __name__ == "__main__":
    module = JumpcloudDirectoryInsightsModule()
    module.register(JumpcloudDirectoryInsightsConnector, "JumpcloudDirectoryInsightsConnector")
    module.run()
