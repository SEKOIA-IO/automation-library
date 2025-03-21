from wiz import WizModule
from wiz.wiz_audit_logs_connector import WizAuditLogsConnector
from wiz.wiz_cloud_configuration_findings_connector import WizCloudConfigurationFindingsConnector
from wiz.wiz_issues_connector import WizIssuesConnector
from wiz.wiz_vulnerability_findings_connector import WizVulnerabilityFindingsConnector

if __name__ == "__main__":
    module = WizModule()
    module.register(WizAuditLogsConnector, "wiz_audit_logs_connector")
    module.register(WizIssuesConnector, "wiz_issues_connector")
    module.register(WizCloudConfigurationFindingsConnector, "wiz_cloud_configuration_findings_connector")
    module.register(WizVulnerabilityFindingsConnector, "wiz_vulnerability_findings_connector")
    module.run()
