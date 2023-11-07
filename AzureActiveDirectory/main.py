from azure_ad.base import AzureADModule
from azure_ad.get_sign_ins import GetSignInsAction, RevokeSignInsSessionsAction
from azure_ad.get_user_authentication_methods import GetUserAuthenticationMethodsAction
from azure_ad.user import DisableUserAction, EnableUserAction, GetUserAction, ResetUserPasswordAction
from azure_ad.delete_app import DeleteApplicationAction

if __name__ == "__main__":
    module = AzureADModule()
    module.register(GetSignInsAction, "GetSignInsAction")
    module.register(EnableUserAction, "EnableUserAction")
    module.register(DisableUserAction, "DisableUserAction")
    module.register(GetUserAuthenticationMethodsAction, "GetUserAuthenticationMethodsAction")
    module.register(GetUserAction, "GetUserAction")
    module.register(ResetUserPasswordAction, "ResetUserPasswordAction")
    module.register(DeleteApplicationAction, "DeleteApplicationAction")
    module.register(RevokeSignInsSessionsAction, "RevokeSignInsSessionsAction")
    module.run()
