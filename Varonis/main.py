from varonis_modules import VaronisModule
from varonis_modules.connector_varonis_saas_alerts import VaronisSaaSAlertsConnector

if __name__ == "__main__":
    module = VaronisModule()
    module.register(VaronisSaaSAlertsConnector, "connector_varonis_saas_alerts")
    module.run()
