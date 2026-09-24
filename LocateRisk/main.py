from locaterisk_modules import LocateRiskModule
from locaterisk_modules.connector_locaterisk_scan_report import LocateRiskScanReportConnector

if __name__ == "__main__":
    module = LocateRiskModule()
    module.register(LocateRiskScanReportConnector, "locaterisk_scan_report")
    module.run()
