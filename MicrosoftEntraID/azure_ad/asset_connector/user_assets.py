import asyncio
from datetime import datetime, timezone
from functools import cached_property
from collections.abc import Generator

from azure.identity.aio import ClientSecretCredential  # async credentials only
from kiota_authentication_azure.azure_identity_authentication_provider import AzureIdentityAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient

from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.user import (
    UserOCSFModel,
    User as UserOCSF,
    Group as UserOCSFGroup,
)
from sekoia_automation.asset_connector.models.ocsf.base import (
    Metadata,
    Product,
)
from sekoia_automation.storage import PersistentJSON

from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph.generated.users.users_request_builder import UsersRequestBuilder
from msgraph.generated.models.software_oath_authentication_method import SoftwareOathAuthenticationMethod
from msgraph.generated.models.microsoft_authenticator_authentication_method import (
    MicrosoftAuthenticatorAuthenticationMethod,
)
from msgraph.generated.models.phone_authentication_method import PhoneAuthenticationMethod
from msgraph.generated.models.group import Group
from msgraph.generated.models.user import User


class EntraIDAssetConnector(AssetConnector):

    PRODUCT_NAME = "Microsoft Entra ID"
    PRODUCT_VERSION = "1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self._client: GraphServiceClient | None = None

    @property
    def most_recent_date_seen(self) -> str | None:
        with self.context as cache:
            most_recent_date_seen = cache.get("most_recent_date_seen", None)

            return most_recent_date_seen

    @cached_property
    def client(self) -> GraphServiceClient:
        if self._client is None:
            credentials = ClientSecretCredential(
                tenant_id=self.module.configuration["tenant_id"],
                client_id=self.module.configuration["client_id"],
                client_secret=self.module.configuration["client_secret"],
            )
            auth_provider = AzureIdentityAuthenticationProvider(credentials)
            adapter = GraphRequestAdapter(auth_provider)
            self._client = GraphServiceClient(request_adapter=adapter)

        return self._client

    def map_fields(self, user: User, has_mfa: bool, groups: list[UserOCSFGroup]) -> UserOCSFModel:
        """Map fields from UserCollectionResponse to UserOCSFModel.
        Args:
            user (UserCollectionResponse): The user data from Microsoft Graph API.

        Returns:
            UserOCSFModel: The mapped OCSF model.
        """
        product = Product(
            name=self.PRODUCT_NAME,
            version=self.PRODUCT_VERSION,
        )
        metadata = Metadata(product=product, version="1.0")
        user_data = UserOCSF(
            has_mfa=has_mfa,
            name=user.user_principal_name or "Unknown",
            uid=0,  # Placeholder, need to change to a unique identifier
            groups=groups,
            full_name=user.display_name or "Unknown",
            email_addr=user.mail or "Unknown",
        )
        user_ocsf_model = UserOCSFModel(
            activity_id=2,
            activity_name="Collect",
            category_name="Discovery",
            category_uid=5,
            class_name="User Inventory Info",
            class_uid=5003,
            type_uid=500302,
            severity="Informational",
            severity_id=1,
            time=datetime.timestamp(user.created_date_time),
            metadata=metadata,
            user=user_data,
            type_name="User Inventory",
        )
        return user_ocsf_model

    async def fetch_user_groups(self, user_id: str) -> list[UserOCSFGroup]:
        """
        Fetch user groups from Microsoft Entra ID.
        """
        groups: list[UserOCSFGroup] = []
        user_groups = await self.client.users.by_user_id(user_id).member_of.get()

        if user_groups:
            for group in user_groups.value:
                if isinstance(group, Group):
                    groups.append(UserOCSFGroup(name=group.display_name, uid=group.id))

        ## Implement if there is more than one page of results
        while user_groups is not None and user_groups.odata_next_link is not None:
            user_groups = (
                await self.client.users.by_user_id(user_id).member_of.with_url(user_groups.odata_next_link).get()
            )
            if user_groups:
                for group in user_groups.value:
                    if isinstance(group, Group):
                        groups.append(UserOCSFGroup(name=group.display_name, uid=group.id))

        return groups

    async def fetch_user_mfa(self, user_id: str) -> bool:
        """
        Fetch MFA status of the user.
        """
        user_mfa = await self.client.users.by_user_id(user_id).authentication.methods.get()
        has_mfa = False
        for method in user_mfa.value:
            if (
                isinstance(method, MicrosoftAuthenticatorAuthenticationMethod)
                or isinstance(method, SoftwareOathAuthenticationMethod)
                or isinstance(method, PhoneAuthenticationMethod)
            ):
                has_mfa = True
                break
        return has_mfa

    async def fetch_user(self, user: User) -> UserOCSFModel:
        """
        Fetch user details and map to UserOCSFModel.
        """
        user_mfa = await self.fetch_user_mfa(user.id)
        user_groups = await self.fetch_user_groups(user.id)
        return self.map_fields(user, user_mfa, user_groups)

    async def fetch_new_users(self, last_run_date: str | None = None) -> list[UserOCSFModel]:
        """
        Fetch new users from Microsoft Entra ID.
        If last_run_date is provided, only fetch users created after that date.
        """
        new_users: list[UserOCSFModel] = []
        query_params = UsersRequestBuilder.UsersRequestBuilderGetQueryParameters(
            select=["id", "displayName", "mail", "identities", "createdDateTime", "userPrincipalName", "mailNickname"],
            filter=f"createdDateTime ge {last_run_date}" if last_run_date else None,
        )

        request_configuration = RequestConfiguration(
            query_parameters=query_params,
        )
        request_configuration.headers.add("ConsistencyLevel", "eventual")

        users = await self.client.users.get(request_configuration=request_configuration)

        if users:
            for user in users.value:
                ## Fetch MFA status of the user
                new_user = await self.fetch_user(user)
                new_users.append(new_user)

        ## Implement if there is more than one page of results
        while users is not None and users.odata_next_link is not None:
            users = await self.client.users.with_url(users.odata_next_link).get(
                request_configuration=request_configuration
            )
            if users:
                for user in users.value:
                    new_user = await self.fetch_user(user)
                    new_users.append(new_user)

        ## Save the most recent date seen
        if new_users:
            most_recent_date: float = max(user.time for user in new_users)
            with self.context as cache:
                cache["most_recent_date_seen"] = (
                    datetime.fromtimestamp(most_recent_date, timezone.utc).replace(microsecond=0).isoformat()
                )
                return new_users

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        ### Fetch users from Microsoft Graph API
        last_run_date: datetime | None = self.most_recent_date_seen if self.most_recent_date_seen else None
        new_users = asyncio.run(self.fetch_new_users(last_run_date=last_run_date))
        for user in new_users:
            yield user
