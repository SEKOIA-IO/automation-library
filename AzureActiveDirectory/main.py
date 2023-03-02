from azure_ad.base import AzureADModule
from azure_ad.get_sign_ins import GetSignInsAction
from azure_ad.get_user_authentication_methods import GetUserAuthenticationMethodsAction
from azure_ad.user import DisableUserAction, EnableUserAction, GetUserAction

if __name__ == "__main__":
    module = AzureADModule()
    module.register(GetSignInsAction, "GetSignInsAction")
    module.register(EnableUserAction, "EnableUserAction")
    module.register(DisableUserAction, "DisableUserAction")
    module.register(GetUserAuthenticationMethodsAction, "GetUserAuthenticationMethodsAction")
    module.register(GetUserAction, "GetUserAction")
    module.run()
