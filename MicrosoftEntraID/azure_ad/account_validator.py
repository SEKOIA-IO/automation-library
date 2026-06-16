import asyncio

from kiota_abstractions.base_request_configuration import RequestConfiguration
from msgraph.generated.users.users_request_builder import UsersRequestBuilder
from sekoia_automation.account_validator import AccountValidator

from azure_ad.base import AzureADModule
from graph_api.client import GraphApi


class AzureADAccountValidator(AccountValidator):
    module: AzureADModule
    _client: GraphApi | None = None

    @property
    def client(self) -> GraphApi:  # pragma: no cover
        if not self._client:
            self._client = GraphApi(
                tenant_id=self.module.configuration.tenant_id,
                client_id=self.module.configuration.client_id,
                client_secret=self.module.configuration.client_secret,
            )

        return self._client

    async def _check_list_users(self) -> str | None:
        query_params = UsersRequestBuilder.UsersRequestBuilderGetQueryParameters(
            select=["id", "signInActivity"],
            top=1,
        )
        config = RequestConfiguration(query_parameters=query_params)
        users = await self.client.client.users.get(request_configuration=config)
        if users and users.value:
            return users.value[0].id
        return None

    async def _check_user_member_of(self, user_id: str) -> None:
        await self.client.client.users.by_user_id(user_id).member_of.get()

    async def _check_user_admin_roles(self, user_id: str) -> None:
        await self.client.client.users.by_user_id(user_id).transitive_member_of.graph_directory_role.get()

    async def _check_user_auth_methods(self, user_id: str) -> None:
        await self.client.client.users.by_user_id(user_id).authentication.methods.get()

    async def _run_all_checks(self) -> bool:
        try:
            user_id = await self._check_list_users()
        except Exception as e:
            self.error(
                f"Permission check failed — List users with signInActivity "
                f"(User.Read.All + AuditLog.Read.All): {e}"
            )
            return False

        if not user_id:
            return True

        per_user_checks = [
            ("List user group memberships (Directory.Read.All)", self._check_user_member_of(user_id)),
            ("List user admin roles (Directory.Read.All)", self._check_user_admin_roles(user_id)),
            (
                "List user authentication methods (UserAuthenticationMethod.Read.All)",
                self._check_user_auth_methods(user_id),
            ),
        ]

        labels = [label for label, _ in per_user_checks]
        coroutines = [coro for _, coro in per_user_checks]

        results = await asyncio.gather(*coroutines, return_exceptions=True)

        all_passed = True
        for label, result in zip(labels, results):
            if isinstance(result, Exception):
                self.error(f"Permission check failed — {label}: {result}")
                all_passed = False

        return all_passed

    def validate(self) -> bool:
        try:
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(self._run_all_checks())
        except Exception as e:
            self.error(f"Impossible to connect to the Azure AD tenant: {e}")
            return False
