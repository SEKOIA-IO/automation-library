from sekoia_automation.module import Module

from fastly_waf.connector_fastly_waf import FastlyWAFConnector

if __name__ == "__main__":
    module = Module()
    module.register(FastlyWAFConnector, "fastly_waf")
    module.run()
