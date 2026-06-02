from zimperium_modules import ZimperiumModule
from zimperium_modules.account_validator import AccountValidator
from zimperium_modules.connector_threats import MobileThreatDefenceConnector

if __name__ == "__main__":
    module = ZimperiumModule()
    module.register_account_validator(AccountValidator)
    module.register(MobileThreatDefenceConnector, "MobileThreatDefenceConnector")
    module.run()
