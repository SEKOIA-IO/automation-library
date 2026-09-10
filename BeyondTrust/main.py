from beyondtrust_modules import BeyondTrustModule
from beyondtrust_modules.connector_pra_platform import BeyondTrustPRAPlatformConnector
from beyondtrust_modules.connector_pra_syslog import BeyondTrustPRASyslogConnector
from beyondtrust_modules.connector_pra_vault_account_activity import BeyondTrustPRAVaultAccountActivityConnector
from beyondtrust_modules.connector_pra_team import BeyondTrustPRATeamConnector

if __name__ == "__main__":
    module = BeyondTrustModule()
    module.register(BeyondTrustPRAPlatformConnector, "connector_beyondtrust_pra")
    module.register(BeyondTrustPRASyslogConnector, "connector_beyondtrust_pra_syslog")
    module.register(BeyondTrustPRAVaultAccountActivityConnector, "connector_beyondtrust_pra_vault_account_activity")
    module.register(BeyondTrustPRATeamConnector, "connector_beyondtrust_pra_team")
    module.run()
