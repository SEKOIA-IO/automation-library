from cyberark_modules import CyberArkModule
from cyberark_modules.connector_audit_logs import CyberArkAuditLogsConnector

if __name__ == "__main__":
    module = CyberArkModule()
    module.register(CyberArkAuditLogsConnector, "connector_audit_logs")
    module.run()
