from thinkst_canary_modules import ThinkstCanaryModule
from thinkst_canary_modules.connector_thinkst_canary_alerts import ThinkstCanaryAlertsConnector

if __name__ == "__main__":
    module = ThinkstCanaryModule()
    module.register(ThinkstCanaryAlertsConnector, "thinkst_canary_alerts")
    module.run()
