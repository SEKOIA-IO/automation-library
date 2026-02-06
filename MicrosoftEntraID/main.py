from azure_ad.account_validator import AzureADAccountValidator
from azure_ad.asset_connector.user_assets import EntraIDAssetConnector
from azure_ad.base import AzureADModule
from azure_ad.connector_entraid_graph_api import MicrosoftEntraIdGraphApiConnector
from azure_ad.delete_app import DeleteApplicationAction
from azure_ad.get_sign_ins import GetSignInsAction, RevokeSignInsSessionsAction
from azure_ad.get_user_authentication_methods import GetUserAuthenticationMethodsAction
from azure_ad.user import (
    DisableUserAction,
    EnableUserAction,
    GetUserAction,
    ResetUserPasswordAction,
    ResetUserPasswordActionV2,
)

if __name__ == "__main__":
    module = AzureADModule()
    module.register_account_validator(AzureADAccountValidator)
    module.register(EntraIDAssetConnector, "entra_id_asset_connector")
    module.register(GetSignInsAction, "GetSignInsAction")
    module.register(EnableUserAction, "EnableUserAction")
    module.register(DisableUserAction, "DisableUserAction")
    module.register(GetUserAuthenticationMethodsAction, "GetUserAuthenticationMethodsAction")
    module.register(GetUserAction, "GetUserAction")
    module.register(ResetUserPasswordAction, "ResetUserPasswordAction")
    module.register(ResetUserPasswordActionV2, "ResetUserPasswordActionV2")
    module.register(DeleteApplicationAction, "DeleteApplicationAction")
    module.register(RevokeSignInsSessionsAction, "RevokeSignInsSessionsAction")
    module.register(MicrosoftEntraIdGraphApiConnector, "entraid_graph_api_connector")
    module.run()
