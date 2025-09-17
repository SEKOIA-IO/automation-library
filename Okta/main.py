from okta_modules import OktaModule
from okta_modules.account_validator import OktaAccountValidator
from okta_modules.system_log_trigger import SystemLogConnector

if __name__ == "__main__":
    module = OktaModule()
    module.register_account_validator(OktaAccountValidator)
    module.register(SystemLogConnector, "okta_system_logs")
    module.run()
