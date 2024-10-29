from microsoft_ad.base import MicrosoftADModule
from microsoft_ad.search import SearchAction
from microsoft_ad.user import (
    ResetUserPasswordAction,
    EnableUserAction,
    DisableUserAction,
)

if __name__ == "__main__":
    module = MicrosoftADModule()
    module.register(EnableUserAction, "EnableUserAction")
    module.register(DisableUserAction, "DisableUserAction")
    module.register(ResetUserPasswordAction, "ResetUserPasswordAction")
    module.register(SearchAction, "search-ad")
    module.run()
