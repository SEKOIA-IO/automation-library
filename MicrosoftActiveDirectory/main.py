from microsoft_ad.account_validator import MicrosoftADAccountValidator
from microsoft_ad.actions_base import MicrosoftADModule
from microsoft_ad.asset_connectors.user_assets import MicrosoftADUserAssetConnector
from microsoft_ad.search_actions import SearchAction
from microsoft_ad.user_actions import DisableUserAction, EnableUserAction, ResetUserPasswordAction

if __name__ == "__main__":
    module = MicrosoftADModule()
    module.register_account_validator(MicrosoftADAccountValidator)
    module.register(MicrosoftADUserAssetConnector, "microsoft_ad_user_assets_connector")
    module.register(EnableUserAction, "EnableUserAction")
    module.register(DisableUserAction, "DisableUserAction")
    module.register(ResetUserPasswordAction, "ResetUserPasswordAction")
    module.register(SearchAction, "search-ad")
    module.run()
