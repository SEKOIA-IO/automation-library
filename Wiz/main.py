from wiz import WizModule
from wiz.wiz_cloud_configuration_findings import WizCloudConfigurationFindingsConnector
from wiz.wiz_issues_connector import WizIssuesConnector

if __name__ == "__main__":
    module = WizModule()
    module.register(WizIssuesConnector, "wiz_issues_connector")
    module.register(WizCloudConfigurationFindingsConnector, "wiz_cloud_configuration_findings_connector")
    module.run()
