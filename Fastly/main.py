from sekoia_automation.module import Module

from fastly.connector_fastly_waf import FastlyWAFConnector
from fastly.connector_fastly_audit import FastlyAuditConnector

if __name__ == "__main__":
    module = Module()
    module.register(FastlyWAFConnector, "fastly_waf")
    module.register(FastlyAuditConnector, "fastly_audit")
    module.run()
