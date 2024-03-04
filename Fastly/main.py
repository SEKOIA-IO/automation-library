from sekoia_automation.module import Module

from fastly.connector_fastly_waf import FastlyWAFConnector
from fastly.connector_fastly_waf_audit import FastlyWAFAuditConnector

if __name__ == "__main__":
    module = Module()
    module.register(FastlyWAFConnector, "fastly_waf")
    module.register(FastlyWAFAuditConnector, "fastly_waf_audit")
    module.run()
