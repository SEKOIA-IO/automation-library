from akamai_modules import AkamaiModule
from akamai_modules.connector_akamai_waf import AkamaiWAFLogsConnector

if __name__ == "__main__":
    module = AkamaiModule()
    module.register(AkamaiWAFLogsConnector, "akamai_waf_logs")
    module.run()
