from zimperium_modules import ZimperiumModule
from zimperium_modules.account_validator import ZimperiumAccountValidator
from zimperium_modules.connector_threats import MobileThreatDefenceConnector

if __name__ == "__main__":
    module = ZimperiumModule()
    module.register_account_validator(ZimperiumAccountValidator)
    module.register(MobileThreatDefenceConnector, "MobileThreatDefenceConnector")
    module.run()
