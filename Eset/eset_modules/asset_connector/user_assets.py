"""ESET user asset connector (ECOS-gated).

ESET Connect API references:
- List users:
  https://help.eset.com/eset_connect/en-US/user_management_v1_users_get.html

- User Management overview:
  https://help.eset.com/eset_connect/en-US/user_management.html

- Authenticate API user (OAuth token):
  https://help.eset.com/eset_connect/en-US/authenticate_api_user.html

- Create API user account (required permissions):
  https://help.eset.com/eset_connect/en-US/create_api_user_account.html

- Requires an ESET Cloud Office Security (ECOS) subscription; users are the
  Microsoft 365 / Google Workspace identities synced via ECOS. Without it the
  endpoint returns 501 Not Implemented:
  https://help.eset.com/ecos/en-US/eset_connect.html

- Release notes (User Management API available with ECOS subscription, ESET Connect 3.3):
  https://help.eset.com/eset_connect/en-US/release_notes.html
"""

from collections.abc import Generator
from datetime import datetime
from functools import cached_property
from typing import Optional
from urllib.parse import urljoin

from pydantic.v1 import ValidationError
from requests.exceptions import HTTPError, RequestException
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.asset_connector.models.ocsf.user import (
    Account,
    AccountTypeId,
    AccountTypeStr,
    User,
    UserEnrichmentObject,
    UserOCSFModel,
)
from sekoia_automation.storage import PersistentJSON

from eset_modules.asset_connector.models import EsetUser, EsetUserPage
from eset_modules.client import ApiClient

# HTTP statuses that mean "user management is not available on this account"
# (no ESET Cloud Office Security subscription). Handle gracefully, don't crash.
ECOS_UNAVAILABLE_STATUSES: frozenset[int] = frozenset({403, 501})


class EsetUserAssetConnector(AssetConnector):

    # Endpoint constants
    USERS_ENDPOINT: str = "/v1/users"
    DEFAULT_PAGE_SIZE: int = 1000

    # Product constants
    PRODUCT_NAME: str = "ESET"
    METADATA_VERSION: str = "1.5.0"

    # OCSF constants
    ACTIVITY_ID: int = 2
    ACTIVITY_NAME: str = "Collect"
    CATEGORY_NAME: str = "Discovery"
    CATEGORY_UID: int = 5
    CLASS_NAME: str = "User Inventory Info"
    CLASS_UID: int = 5003
    TYPE_NAME: str = "User Inventory Info: Collect"
    TYPE_UID: int = 500302

    # ESET identity provider type -> OCSF account type
    ACCOUNT_TYPE_MAP: dict[str, tuple[AccountTypeStr, AccountTypeId]] = {
        "MICROSOFT": (AccountTypeStr.M365_TENANT, AccountTypeId.M365_TENANT),
        "M365": (AccountTypeStr.M365_TENANT, AccountTypeId.M365_TENANT),
        "OFFICE365": (AccountTypeStr.M365_TENANT, AccountTypeId.M365_TENANT),
        "AZURE": (AccountTypeStr.AZURE_AD_ACCOUNT, AccountTypeId.AZURE_AD_ACCOUNT),
        "GOOGLE": (AccountTypeStr.GOOGLE_WORKSPACE, AccountTypeId.GOOGLE_WORKSPACE),
        "GSUITE": (AccountTypeStr.GOOGLE_WORKSPACE, AccountTypeId.GOOGLE_WORKSPACE),
        "WORKSPACE": (AccountTypeStr.GOOGLE_WORKSPACE, AccountTypeId.GOOGLE_WORKSPACE),
    }

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("eset_user_context.json", self._data_path)
        self._latest_time: Optional[str] = None

    @cached_property
    def base_url(self) -> str:
        region = self.module.configuration.region
        return f"https://{region}.user-management.eset.systems"

    @cached_property
    def client(self) -> ApiClient:
        region = self.module.configuration.region
        return ApiClient(
            auth_base_url=f"https://{region}.business-account.iam.eset.systems",
            username=self.module.configuration.username,
            password=self.module.configuration.password,
        )

    @cached_property
    def metadata(self) -> Metadata:
        return Metadata(
            product=Product(name=self.PRODUCT_NAME),
            version=self.METADATA_VERSION,
        )

    def _resolve_account_type(self, user: EsetUser) -> tuple[AccountTypeStr, AccountTypeId]:
        """Infer the OCSF account type from the user's identity providers."""
        if user.identities:
            for identity in user.identities:
                if not identity.type:
                    continue
                key = identity.type.upper()
                for token, mapped in self.ACCOUNT_TYPE_MAP.items():
                    if token in key:
                        return mapped
        return AccountTypeStr.OTHER, AccountTypeId.OTHER

    @staticmethod
    def _build_enrichments(user: EsetUser) -> Optional[list[UserEnrichmentObject]]:
        enrichments: list[UserEnrichmentObject] = []
        for name, value in (
            ("department", user.department),
            ("job_title", user.jobTitle),
            ("office_location", user.officeLocation),
            ("protection_status", user.protectionStatus),
        ):
            if value:
                enrichments.append(UserEnrichmentObject(name=name, value=value))
        return enrichments or None

    def map_fields(self, user: EsetUser) -> UserOCSFModel:
        """Map an ESET user to a full OCSF UserOCSFModel."""
        name = user.displayName or user.primaryEmailAddress or user.uuid
        account_type_str, account_type_id = self._resolve_account_type(user)

        groups = None
        if user.userGroupUuids:
            groups = [Group(name=uuid, uid=uuid) for uuid in user.userGroupUuids]

        ocsf_user = User(
            name=name,
            uid=user.uuid,
            email_addr=user.primaryEmailAddress,
            display_name=user.displayName,
            groups=groups,
            account=Account(
                name=name,
                uid=user.uuid,
                type=account_type_str,
                type_id=account_type_id,
            ),
        )

        return UserOCSFModel(
            activity_id=self.ACTIVITY_ID,
            activity_name=self.ACTIVITY_NAME,
            category_name=self.CATEGORY_NAME,
            category_uid=self.CATEGORY_UID,
            class_name=self.CLASS_NAME,
            class_uid=self.CLASS_UID,
            type_name=self.TYPE_NAME,
            type_uid=self.TYPE_UID,
            time=datetime.now().astimezone().timestamp(),
            metadata=self.metadata,
            user=ocsf_user,
            enrichments=self._build_enrichments(user),
        )

    def _fetch_users(self) -> Generator[list[EsetUser], None, None]:
        """Fetch all users with pagination. ECOS-gated: 403/501 yield nothing (no crash)."""
        url = urljoin(self.base_url, self.USERS_ENDPOINT)
        params: dict[str, str | int] = {"pageSize": self.DEFAULT_PAGE_SIZE}

        self.log("Fetching ESET users", level="info")

        try:
            page_number = 1
            while self.running:
                response = self.client.get(url, params=params, timeout=60)

                if response.status_code in ECOS_UNAVAILABLE_STATUSES:
                    self.log(
                        "ESET user management is unavailable on this account "
                        f"(HTTP {response.status_code}). This API requires an ESET Cloud Office Security "
                        "(ECOS) subscription — no users returned.",
                        level="warning",
                    )
                    return

                response.raise_for_status()
                raw = response.json()

                try:
                    page = EsetUserPage.parse_obj(raw)
                except ValidationError as e:
                    self.log(f"Failed to parse users page {page_number}: {e}", level="warning")
                    break

                self.log(f"Retrieved page {page_number} - {len(page.users)} users", level="info")

                if not page.users:
                    break

                yield page.users

                if not page.nextPageToken:
                    self.log(f"Pagination complete after {page_number} pages", level="info")
                    break

                params = {"pageSize": self.DEFAULT_PAGE_SIZE, "pageToken": page.nextPageToken}
                page_number += 1

        except HTTPError as e:
            status = e.response.status_code if e.response is not None else None
            if status in ECOS_UNAVAILABLE_STATUSES:
                self.log(
                    f"ESET user management is unavailable on this account (HTTP {status}). "
                    "This API requires an ESET Cloud Office Security (ECOS) subscription — no users returned.",
                    level="warning",
                )
                return
            self.log(f"API request failed while fetching users: {e}", level="error")
            raise
        except RequestException as e:
            self.log(f"API request failed while fetching users: {e}", level="error")
            raise

    def update_checkpoint(self) -> None:
        """Users carry no modified-time field; store a last-run marker only."""
        if self._latest_time:
            with self.context as cache:
                cache["last_run"] = self._latest_time
            self.log(f"Checkpoint updated to: {self._latest_time}", level="debug")

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        """Main entry point. Fetch ESET users and yield OCSF UserOCSFModel instances."""
        self.log("Starting ESET user asset collection", level="info")

        assets_generated = 0
        assets_skipped = 0

        try:
            for users in self._fetch_users():
                for user in users:
                    try:
                        yield self.map_fields(user)
                        assets_generated += 1
                    except (KeyError, ValueError) as e:
                        assets_skipped += 1
                        self.log(f"Asset skipped - UUID: {user.uuid}, Reason: {e}", level="warning")
                        continue

            self._latest_time = datetime.now().astimezone().isoformat()
            self.log(
                f"Asset collection complete - Generated: {assets_generated}, Skipped: {assets_skipped}",
                level="info",
            )

        except Exception as e:
            self.log(
                f"Asset collection failed - Generated: {assets_generated}, Skipped: {assets_skipped}, Error: {e}",
                level="error",
            )
            raise
