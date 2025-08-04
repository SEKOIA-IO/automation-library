from beyondtrust_modules import BeyondTrustModule
from beyondtrust_modules.connector_pra_platform import BeyondTrustPRAPlatformConnector

if __name__ == "__main__":
    module = BeyondTrustModule()
    module.register(BeyondTrustPRAPlatformConnector, "connector_beyondtrust_pra")
    module.run()
