import time
from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone

from azure.identity.aio import ClientSecretCredential  # async credentials only
from kiota_abstractions.api_error import APIError
from kiota_abstractions.base_request_configuration import RequestConfiguration
from kiota_authentication_azure.azure_identity_authentication_provider import AzureIdentityAuthenticationProvider
from msgraph import GraphRequestAdapter, GraphServiceClient
from msgraph.generated.models.group import Group
from msgraph.generated.models.microsoft_authenticator_authentication_method import (
    MicrosoftAuthenticatorAuthenticationMethod,
)
from msgraph.generated.models.phone_authentication_method import PhoneAuthenticationMethod
from msgraph.generated.models.software_oath_authentication_method import SoftwareOathAuthenticationMethod
from msgraph.generated.models.user import User
from msgraph.generated.users.users_request_builder import UsersRequestBuilder
from sekoia_automation.asset_connector import AsyncAssetConnector
from sekoia_automation.asset_connector.models.connector import DefaultAssetConnectorConfiguration
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.organization import Organization
from sekoia_automation.asset_connector.models.ocsf.user import (
    Account,
    AccountTypeId,
    AccountTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.user import Group as UserOCSFGroup
from sekoia_automation.asset_connector.models.ocsf.user import User as UserOCSF
from sekoia_automation.asset_connector.models.ocsf.user import (
    UserDataObject,
    UserEnrichmentObject,
    UserOCSFModel,
    UserTypeId,
    UserTypeStr,
)
from sekoia_automation.storage import PersistentJSON

from azure_ad.base import AzureADModule


class EntraIDAssetConnectorConfiguration(DefaultAssetConnectorConfiguration):
    refresh_users_per_cycle: int = 1000


class EntraIDAssetConnector(AsyncAssetConnector):
    """Asset connector for Microsoft Entra ID user inventory.

    Fetches user information, groups, MFA status, and admin roles from
    Microsoft Entra ID (formerly Azure AD) and maps them to OCSF format.
    """

    module: AzureADModule
    configuration: EntraIDAssetConnectorConfiguration

    PRODUCT_NAME = "Microsoft Entra ID"
    PRODUCT_VERSION = "1.0"
    # Graph caps a page of users at 999 items
    MAX_PAGE_SIZE = 999
    # Users kept next to the creation-date checkpoint, to skip the ones already collected at that date
    MAX_CHECKPOINT_IDS = 1000
    # Lower bound of the refresh walk: a date filter keeps users without a creation date out of it
    REFRESH_WALK_START = "1970-01-01T00:00:00+00:00"
    # Graph answers a user that cannot be read with 403 (management-restricted account)
    # or 404 (deleted since the listing). Any other error is not about the user.
    UNREADABLE_USER_STATUSES = (403, 404)
    USER_SELECT_FIELDS = [
        "id",
        "displayName",
        "mail",
        "identities",
        "createdDateTime",
        "userPrincipalName",
        "mailNickname",
        "accountEnabled",
        "department",
        "jobTitle",
        "employeeId",
        "employeeType",
        "signInActivity",
        "companyName",
        "officeLocation",
        "isManagementRestricted",
        "lastPasswordChangeDateTime",
        "onPremisesSamAccountName",
    ]

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self._client: GraphServiceClient | None = None
        self._credentials: ClientSecretCredential | None = None
        self._latest_date: str | None = None
        self._latest_date_ids: list[str] = []
        self._pending_refresh_cursor: str | None = None
        self._pending_refresh_completed_at: float | None = None

    @property
    def most_recent_date_seen(self) -> str | None:
        with self.context as cache:
            most_recent_date_seen: str | None = cache.get("most_recent_date_seen", None)

            return most_recent_date_seen

    @property
    def most_recent_date_seen_ids(self) -> list[str]:
        """Ids of the users already collected at `most_recent_date_seen`.

        The filter on that date is `ge`, not `gt`: a user created in the same second as
        the last one seen, but after it, would be skipped for good otherwise. These ids
        are what keeps the inclusive filter from collecting the same users twice.
        """
        with self.context as cache:
            most_recent_date_seen_ids: list[str] = list(cache.get("most_recent_date_seen_ids", []))

            return most_recent_date_seen_ids

    @property
    def refresh_cursor_date(self) -> str | None:
        """Creation date where the next refresh cycle resumes, None to start from the oldest user."""
        with self.context as cache:
            refresh_cursor_date: str | None = cache.get("refresh_cursor_date", None) or None

            return refresh_cursor_date

    @property
    def last_refresh_completed_at(self) -> float:
        """Time the last refresh walk reached the end of the inventory, 0 if none did."""
        with self.context as cache:
            last_refresh_completed_at: float = cache.get("last_refresh_completed_at", 0.0)

            return last_refresh_completed_at

    @property
    def client(self) -> GraphServiceClient:
        if self._client is None:
            self._credentials = ClientSecretCredential(
                tenant_id=self.module.configuration.tenant_id,
                client_id=self.module.configuration.client_id,
                client_secret=self.module.configuration.client_secret,
            )
            auth_provider = AzureIdentityAuthenticationProvider(self._credentials)
            adapter = GraphRequestAdapter(auth_provider)
            self._client = GraphServiceClient(request_adapter=adapter)

        return self._client

    @client.setter
    def client(self, value: GraphServiceClient) -> None:
        self._client = value

    async def close_client(self) -> None:
        """Close the Graph client and credentials to release HTTP transport resources."""
        if self._credentials is not None:
            await self._credentials.close()
            self._credentials = None
        self._client = None

    @staticmethod
    def checkpoint_date(date: datetime | None) -> str | None:
        """Format a creation date the way the checkpoint and the Graph filter express it."""
        if date is None:
            return None

        return date.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    def save_refresh_progress(self, cursor: str | None, completed_at: float | None) -> None:
        if cursor is None and completed_at is None:
            return
        with self.context as cache:
            if cursor is not None:
                cache["refresh_cursor_date"] = cursor
            if completed_at is not None:
                cache["last_refresh_completed_at"] = completed_at

    async def update_checkpoint(self) -> None:
        if self._latest_date is not None:
            with self.context as cache:
                cache["most_recent_date_seen"] = self._latest_date
                cache["most_recent_date_seen_ids"] = self._latest_date_ids
        self.save_refresh_progress(self._pending_refresh_cursor, self._pending_refresh_completed_at)
        self._pending_refresh_cursor = None
        self._pending_refresh_completed_at = None

    async def reset_checkpoint(self) -> None:
        with self.context as cache:
            cache.pop("most_recent_date_seen", None)
            cache.pop("most_recent_date_seen_ids", None)
            cache.pop("refresh_cursor_date", None)
            cache.pop("last_refresh_completed_at", None)
        self._latest_date = None
        self._latest_date_ids = []
        self._pending_refresh_cursor = None
        self._pending_refresh_completed_at = None

    def get_mapped_fields(self) -> dict[str, str]:
        return {
            "id": "user.uid",
            "display_name": "user.full_name",
            "mail": "user.email_addr",
            "user_principal_name": "user.name",
            "company_name": "user.org.name",
            "office_location": "user.org.ou_name",
            "on_premises_sam_account_name": "user.uid_alt",
            "account_enabled": "enrichments.account.data.is_enabled",
            "department": "enrichments.employment.value",
            "job_title": "enrichments.employment.value",
            "sign_in_activity.last_sign_in_date_time": "enrichments.account.data.last_logon",
            "last_password_change_date_time": "enrichments.account.data.last_time_password_change",
            "created_date_time": "time",
        }

    def map_fields(self, user: User, has_mfa: bool, groups: list[UserOCSFGroup], is_admin: bool) -> UserOCSFModel:
        """Map fields from User to UserOCSFModel.

        Args:
            user: The user data from Microsoft Graph API.
            has_mfa: Whether the user has MFA enabled.
            groups: List of user groups.
            is_admin: Whether the user has admin roles.

        Returns:
            UserOCSFModel: The mapped OCSF model.
        """
        product = Product(
            name=self.PRODUCT_NAME,
            version=self.PRODUCT_VERSION,
        )
        metadata = Metadata(product=product, version="1.6.0")

        # Extract domain from userPrincipalName
        domain = None
        if user.user_principal_name and "@" in user.user_principal_name:
            domain = user.user_principal_name.split("@")[1]

        # Determine user type based on employee type or job title
        user_type_id = UserTypeId.USER
        user_type_str = UserTypeStr.USER

        if is_admin:
            user_type_id = UserTypeId.ADMIN
            user_type_str = UserTypeStr.ADMIN

        # Create organization object if company name is available
        org = None
        if user.company_name:
            org = Organization(
                name=user.company_name,
                ou_name=user.office_location,
            )

        account = Account(
            name=user.user_principal_name or "Unknown",
            type_id=AccountTypeId.AZURE_AD_ACCOUNT,
            type=AccountTypeStr.AZURE_AD_ACCOUNT,
            uid=user.id,
        )
        user_data = UserOCSF(
            has_mfa=has_mfa,
            name=user.user_principal_name or "Unknown",
            uid=user.id,
            groups=groups,
            full_name=user.display_name or "Unknown",
            email_addr=user.mail or "Unknown",
            account=account,
            display_name=user.display_name,
            domain=domain,
            type_id=user_type_id,
            type=user_type_str,
            org=org,
            uid_alt=user.on_premises_sam_account_name,
        )

        # Build enrichment data
        enrichments = []

        # Create user data object with account status and login information
        user_data_obj = UserDataObject(
            is_enabled=user.account_enabled if user.account_enabled is not None else None,
            last_logon=(
                user.sign_in_activity.last_sign_in_date_time.isoformat()
                if user.sign_in_activity and user.sign_in_activity.last_sign_in_date_time
                else None
            ),
            last_time_password_change=(
                user.last_password_change_date_time.timestamp() if user.last_password_change_date_time else None
            ),
        )

        # Add account status enrichment
        enrichments.append(
            UserEnrichmentObject(
                name="account",
                value="status",
                data=user_data_obj,
            )
        )

        # Add employment info enrichment if available
        if user.department or user.job_title or user.employee_id or user.employee_type:
            employment_data = UserDataObject()
            employment_enrichment = UserEnrichmentObject(
                name="employment",
                value=f"{user.department or ''} - {user.job_title or ''}".strip(" -") or "info",
                data=employment_data,
            )
            enrichments.append(employment_enrichment)

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
            time=datetime.timestamp(user.created_date_time) if user.created_date_time is not None else 0,
            metadata=metadata,
            user=user_data,
            type_name="User Inventory Info: Collect",
            enrichments=enrichments or None,
        )
        return user_ocsf_model

    async def fetch_user_groups(self, user_id: str) -> list[UserOCSFGroup]:
        """
        Fetch user groups from Microsoft Entra ID.
        """
        groups: list[UserOCSFGroup] = []
        try:
            user_groups = await self.client.users.by_user_id(user_id).member_of.get()
            if user_groups and user_groups.value:
                for group in user_groups.value:
                    if isinstance(group, Group):
                        groups.append(UserOCSFGroup(name=group.display_name, uid=group.id))

            # Handle pagination for multiple pages of results
            while user_groups is not None and user_groups.odata_next_link is not None:
                user_groups = (
                    await self.client.users.by_user_id(user_id).member_of.with_url(user_groups.odata_next_link).get()
                )
                if user_groups and user_groups.value:
                    for group in user_groups.value:
                        if isinstance(group, Group):
                            groups.append(UserOCSFGroup(name=group.display_name, uid=group.id))

            return groups
        except Exception as e:
            raise ValueError(f"Error fetching user groups: {e}") from e

    async def fetch_user_admin_roles(self, user_id: str) -> bool:
        """
        Fetch admin roles of the user.
        """
        try:
            user_roles = await self.client.users.by_user_id(user_id).transitive_member_of.graph_directory_role.get()
            return bool(user_roles and user_roles.value)
        except Exception as e:
            raise ValueError(f"Error fetching user admin roles: {e}") from e

    async def fetch_user_mfa(self, user_id: str) -> bool:
        """
        Fetch MFA status of the user.
        """
        try:
            user_mfa = await self.client.users.by_user_id(user_id).authentication.methods.get()
            has_mfa = False
            if user_mfa and user_mfa.value:
                for method in user_mfa.value:
                    if isinstance(
                        method,
                        (
                            MicrosoftAuthenticatorAuthenticationMethod,
                            SoftwareOathAuthenticationMethod,
                            PhoneAuthenticationMethod,
                        ),
                    ):
                        has_mfa = True
                        break
            return has_mfa
        except Exception as e:
            raise ValueError(f"Error fetching user MFA: {e}") from e

    async def fetch_user(self, user: User) -> UserOCSFModel:
        """
        Fetch user details and map to UserOCSFModel.
        """
        user_mfa = False
        user_groups = []
        is_admin = False

        if user.id:
            user_mfa = await self.fetch_user_mfa(user.id)
            user_groups = await self.fetch_user_groups(user.id)
            is_admin = await self.fetch_user_admin_roles(user.id)
        return self.map_fields(user, user_mfa, user_groups, is_admin)

    @classmethod
    def is_unreadable_user_error(cls, error: BaseException) -> bool:
        cause: BaseException | None = error
        while cause is not None:
            if isinstance(cause, APIError):
                return cause.response_status_code in cls.UNREADABLE_USER_STATUSES
            cause = cause.__cause__
        return False

    async def fetch_user_or_skip(self, user: User) -> UserOCSFModel | None:
        """Fetch a user's details, None when Graph refuses to read that user.

        A user that cannot be read must not abort the cycle: the next one would retry it
        right away. No fallback asset either, a wrong `has_mfa=False` is worse than a stale
        one. Other errors (outage, throttling) are raised: skipping on them would move the
        checkpoints past users that are readable.
        """
        try:
            return await self.fetch_user(user)
        except Exception as e:
            if not self.is_unreadable_user_error(e):
                raise
            self.log(message=f"Skipping user {user.id}: {e}", level="error")
            return None

    async def list_users(self, user_filter: str | None, limit: int | None = None) -> AsyncGenerator[User, None]:
        """
        List users from Microsoft Entra ID, oldest first, following pagination.
        Stop after `limit` users when one is given.
        """
        query_params = UsersRequestBuilder.UsersRequestBuilderGetQueryParameters(
            select=self.USER_SELECT_FIELDS,
            filter=user_filter,
            orderby=["createdDateTime asc"],
            count=True,
            top=min(limit, self.MAX_PAGE_SIZE) if limit is not None else None,
        )

        request_configuration = RequestConfiguration(
            query_parameters=query_params,
        )
        request_configuration.headers.add("ConsistencyLevel", "eventual")

        users = await self.client.users.get(request_configuration=request_configuration)
        listed = 0
        while users is not None:
            for user in users.value or []:
                yield user
                listed += 1
                if limit is not None and listed >= limit:
                    return

            if users.odata_next_link is None:
                return

            # Create a new config for pagination that preserves headers but NOT query params
            pagination_config: RequestConfiguration = RequestConfiguration()
            pagination_config.headers.add("ConsistencyLevel", "eventual")
            users = await self.client.users.with_url(users.odata_next_link).get(
                request_configuration=pagination_config
            )

    def record_new_user(self, user: User) -> None:
        """Move the creation-date checkpoint to a user, before it is yielded."""
        date = self.checkpoint_date(user.created_date_time)
        if date is None or user.id is None:
            return

        if date != self._latest_date:
            self._latest_date = date
            self._latest_date_ids = []
        self._latest_date_ids.append(user.id)
        del self._latest_date_ids[: -self.MAX_CHECKPOINT_IDS]

    async def fetch_new_users(self, last_run_date: str | None = None) -> AsyncGenerator[UserOCSFModel, None]:
        """
        Fetch new users from Microsoft Entra ID.
        If last_run_date is provided, only fetch users created at or after that date,
        skipping the ones already collected at that exact date.
        """
        already_collected = set(self.most_recent_date_seen_ids) if last_run_date else set()
        try:
            async for user in self.list_users(f"createdDateTime ge {last_run_date}" if last_run_date else None):
                if user.id in already_collected:
                    continue

                # Fetch user details including MFA status
                new_user = await self.fetch_user_or_skip(user)
                # Recorded before the yield: the consumer checkpoints the batch holding
                # this user before asking for another one. A skipped user is recorded too,
                # the refresh walk retries it.
                self.record_new_user(user)
                if new_user is not None:
                    yield new_user
        except Exception as e:
            raise ValueError(f"Error fetching users: {e}") from e

    def next_refresh_cursor(self, users: list[User], cursor: str | None, slice_size: int) -> str:
        """Creation date where the next cycle resumes the refresh walk, "" to start over."""
        if len(users) < slice_size:
            # End of the inventory: walk it again from the oldest user
            return ""

        last_date = self.checkpoint_date(users[-1].created_date_time)
        if last_date is None:
            return ""

        if last_date == cursor:
            # The walk resumes with `ge`, so a creation date shared by more users than a
            # slice holds would repeat forever. Skipping past it keeps the walk moving;
            # raising refresh_users_per_cycle covers the users left behind.
            self.log(
                message=(
                    f"More than {slice_size} users were created on {cursor}: "
                    "the ones past that count are not refreshed"
                ),
                level="warning",
            )
            return self.checkpoint_date(datetime.fromisoformat(cursor) + timedelta(seconds=1)) or ""

        return last_date

    async def fetch_refreshed_users(self, excluded_user_ids: set[str]) -> AsyncGenerator[UserOCSFModel, None]:
        """
        Re-fetch a slice of the users already collected, oldest first.

        `createdDateTime` never changes, so the incremental query never returns a user
        twice. Without this walk, changes to account status, groups, admin roles or MFA
        would never reach the inventory. One slice per cycle keeps the sync incremental.

        A walk starts at most once per `frequency`. The SDK only sleeps after a cycle that
        yielded nothing, so a walk restarting as soon as it ends would never let it sleep.
        """
        slice_size = self.configuration.refresh_users_per_cycle
        if slice_size <= 0:
            return

        cursor = self.refresh_cursor_date
        if cursor is None and time.time() - self.last_refresh_completed_at < self.frequency:
            return

        # Graph does not document where users without a creation date sort, and a date
        # cursor cannot reach them: they get their own pass at the start of each walk.
        # Best effort: a failure there must not hold back the dated walk.
        # ponytail: listed in one go, page them with their own cursor if a tenant has thousands
        undated_users: list[User] = []
        if not cursor:
            try:
                undated_users = [user async for user in self.list_users("createdDateTime eq null")]
            except Exception as e:
                self.log(message=f"Error fetching users without creation date: {e}", level="warning")

        # An error stops the refresh only: the new users of the cycle are still pushed,
        # and the walk resumes from the same cursor on the next cycle
        try:
            users = [
                user
                async for user in self.list_users(
                    f"createdDateTime ge {cursor or self.REFRESH_WALK_START}", limit=slice_size
                )
            ]
        except Exception as e:
            self.log(message=f"Error fetching users to refresh: {e}", level="error")
            return

        if undated_users:
            self.log(message=f"{len(undated_users)} users have no creation date", level="info")

        next_cursor = self.next_refresh_cursor(users, cursor, slice_size)
        completed_at = time.time() if next_cursor == "" else None

        # One asset behind: the cursor that ends the slice must ride with the last asset
        # actually yielded, which is only known once every later user was fetched or skipped
        previous: tuple[str | None, UserOCSFModel] | None = None
        for user in undated_users + users:
            if user.id in excluded_user_ids:
                continue
            try:
                asset = await self.fetch_user_or_skip(user)
            except Exception as e:
                # Stop at this user, not past it: the walk resumes from the last asset yielded
                self.log(message=f"Refresh stopped at user {user.id}: {e}", level="error")
                if previous is not None:
                    self._pending_refresh_cursor = previous[0]
                    yield previous[1]
                return
            if asset is None:
                continue
            if previous is not None:
                self._pending_refresh_cursor = previous[0]
                yield previous[1]
            previous = (self.checkpoint_date(user.created_date_time), asset)

        if previous is None:
            # Nothing to push, so no push to save the progress
            self.save_refresh_progress(next_cursor, completed_at)
            return

        # Set before the last yield, not after: the consumer pushes the batch holding that
        # user before asking for another asset, and asks for none when the refreshed users
        # exactly fill it. update_checkpoint saves the cursor when that push succeeds.
        self._pending_refresh_cursor = next_cursor
        self._pending_refresh_completed_at = completed_at
        yield previous[1]

    async def get_assets(self) -> AsyncGenerator[UserOCSFModel, None]:
        """Fetch user assets from Microsoft Graph API.

        Yields:
            UserOCSFModel: OCSF-formatted user inventory data.
        """
        # Fetch users from Microsoft Graph API
        last_run_date: str | None = self.most_recent_date_seen
        self._latest_date = last_run_date
        self._latest_date_ids = self.most_recent_date_seen_ids
        # Left over by a push that failed without raising: must not ride with the next one.
        # The walk also sits this cycle out, so a failing push does not re-enrich the same
        # slice right away; with no new users the cycle yields nothing and the SDK sleeps.
        refresh_push_failed = (
            self._pending_refresh_cursor is not None or self._pending_refresh_completed_at is not None
        )
        self._pending_refresh_cursor = None
        self._pending_refresh_completed_at = None
        try:
            sent_user_ids: set[str] = set()
            async for user in self.fetch_new_users(last_run_date=last_run_date):
                if user.user.uid:
                    sent_user_ids.add(user.user.uid)
                yield user

            if refresh_push_failed:
                self.log(message="Last refresh push failed: refresh resumes on the next cycle", level="warning")
                return

            async for user in self.fetch_refreshed_users(sent_user_ids):
                yield user
        finally:
            await self.close_client()
