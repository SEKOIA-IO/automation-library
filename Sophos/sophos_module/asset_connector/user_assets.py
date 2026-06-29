from collections.abc import Generator
from datetime import datetime, timezone
from functools import cached_property
from typing import Any

from dateutil.parser import isoparse
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.asset_connector.models.ocsf.organization import Organization
from sekoia_automation.asset_connector.models.ocsf.user import (
    Account,
    AccountTypeId,
    AccountTypeStr,
    User,
    UserOCSFModel,
    UserTypeId,
    UserTypeStr,
)
from sekoia_automation.storage import PersistentJSON

from sophos_module.asset_connector.model import SophosUser, SophosUsersResponse
from sophos_module.client import SophosApiClient
from sophos_module.client.auth import SophosApiAuthentication

_CACHE_KEY = "known_users"


class SophosUserAssetConnector(AssetConnector):
    """
    Asset connector for Sophos directory users.
    Collects user accounts from the Sophos Central API via GET /common/v1/directory/users.

    Because the API provides no server-side date filter, the connector maintains a
    local cache of ``{user_id: updatedAt}`` in ``user_context.json``.  On each run it
    fetches every page, compares each user's ``updatedAt`` (or ``createdAt``) against
    the cache, and only yields users that are **new or changed**.  After a successful
    run the cache is replaced with the full current snapshot so deleted users are
    eventually evicted.
    """

    PRODUCT_NAME: str = "Sophos EDR"
    PRODUCT_VERSION: str = "N/A"
    OCSF_VERSION: str = "1.6.0"
    PAGE_SIZE: int = 100

    # OCSF Constants
    ACTIVITY_ID: int = 2
    ACTIVITY_NAME: str = "Collect"
    CATEGORY_NAME: str = "Discovery"
    CATEGORY_UID: int = 5
    CLASS_NAME: str = "User Inventory Info"
    CLASS_UID: int = 5003
    TYPE_NAME: str = "User Inventory Info: Collect"
    TYPE_UID: int = 500302

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("user_context.json", self._data_path)
        # Snapshot of the full current run: id → updatedAt (or createdAt fallback)
        self._current_run: dict[str, str] = {}

    @property
    def _known_users(self) -> dict[str, str]:
        """Return the cached id→timestamp map from the previous run."""
        with self.context as cache:
            return dict(cache.get(_CACHE_KEY) or {})

    @cached_property
    def client(self) -> SophosApiClient:
        cfg = self.module.configuration
        auth = SophosApiAuthentication(
            api_host=cfg.api_host,
            authorization_url=cfg.oauth2_authorization_url,
            client_id=cfg.client_id,
            client_secret=cfg.client_secret,
        )
        return SophosApiClient(auth=auth)

    @cached_property
    def metadata(self) -> Metadata:
        return Metadata(
            product=Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION),
            version=self.OCSF_VERSION,
        )

    @staticmethod
    def _parse_ts(ts: str | None) -> float | None:
        if not ts:
            return None
        try:
            return isoparse(ts).timestamp()
        except (ValueError, AttributeError):
            return None

    @staticmethod
    def _user_timestamp(user: SophosUser) -> str | None:
        """Return the best available timestamp string for change-detection purposes."""
        return user.updatedAt or user.createdAt

    @staticmethod
    def _get_account_type(user: SophosUser) -> tuple[AccountTypeId, AccountTypeStr]:
        """Infer account type from available fields.

        - name like 'DOMAIN\\username' (backslash) and no email → Windows account
        - otherwise → Unknown
        """
        name = user.name or ""
        if "\\" in name and not user.email:
            return AccountTypeId.WINDOWS_ACCOUNT, AccountTypeStr.WINDOWS_ACCOUNT
        return AccountTypeId.UNKNOWN, AccountTypeStr.UNKNOWN

    @staticmethod
    def _get_groups(user: SophosUser) -> list[Group] | None:
        if not user.groups or not user.groups.items:
            return None
        groups = [Group(uid=g.id, name=g.name or g.displayName or "") for g in user.groups.items if g.id]
        return groups if groups else None

    @staticmethod
    def _get_organization(user: SophosUser) -> Organization | None:
        if user.tenant and user.tenant.id:
            return Organization(uid=user.tenant.id, name=user.tenant.id)
        return None

    def _is_new_or_changed(self, user: SophosUser, known: dict[str, str]) -> bool:
        """Return True when the user is not yet cached or its timestamp has changed."""
        if not user.id:
            return True
        cached_ts = known.get(user.id)
        if cached_ts is None:
            return True
        current_ts = self._user_timestamp(user) or ""
        return current_ts != cached_ts

    def map_user_fields(self, user: SophosUser) -> UserOCSFModel | None:
        """Map a Sophos directory user to an OCSF UserOCSFModel.

        Returns None if mandatory fields are missing.
        """
        uid = user.id
        name = user.name

        if not uid:
            self.log(f"Skipping user: missing 'id'. Data: {user}", level="warning")
            return None
        if not name:
            self.log(f"Skipping user {uid}: missing 'name'", level="warning")
            return None

        account_type_id, account_type_str = self._get_account_type(user)
        groups = self._get_groups(user)
        org = self._get_organization(user)

        # Build full name from firstName + lastName when available
        full_name: str | None = None
        if user.firstName or user.lastName:
            full_name = " ".join(filter(None, [user.firstName, user.lastName])) or None

        account = Account(
            name=name,
            type_id=account_type_id,
            type=account_type_str,
            uid=uid,
        )

        ocsf_user = User(
            uid=uid,
            name=name,
            full_name=full_name,
            email_addr=user.email if user.email else None,
            account=account,
            groups=groups,
            org=org,
            type_id=UserTypeId.USER,
            type=UserTypeStr.USER,
        )

        # Event time: prefer updatedAt, fallback to createdAt, then now
        updated_ts = self._parse_ts(user.updatedAt)
        created_ts = self._parse_ts(user.createdAt)
        event_time = updated_ts or created_ts or datetime.now(tz=timezone.utc).timestamp()

        return UserOCSFModel(
            activity_id=self.ACTIVITY_ID,
            activity_name=self.ACTIVITY_NAME,
            category_name=self.CATEGORY_NAME,
            category_uid=self.CATEGORY_UID,
            class_name=self.CLASS_NAME,
            class_uid=self.CLASS_UID,
            type_name=self.TYPE_NAME,
            type_uid=self.TYPE_UID,
            severity="Informational",
            severity_id=1,
            time=event_time,
            metadata=self.metadata,
            user=ocsf_user,
        )

    def _fetch_all_pages(self) -> Generator[SophosUser, None, None]:
        """Yield every user returned by the API across all pages."""
        page = 1

        while self.running:
            params: dict[str, Any] = {
                "pageSize": self.PAGE_SIZE,
                "page": page,
            }
            response = self.client.list_directory_users(params)
            response.raise_for_status()
            data: SophosUsersResponse = SophosUsersResponse.model_validate(response.json())

            yield from data.items

            # Stop if we received fewer items than the page size (last page)
            page_size = (data.pages.size or self.PAGE_SIZE) if data.pages else self.PAGE_SIZE
            if len(data.items) < page_size:
                break

            page += 1

    def _iter_users(self) -> Generator[SophosUser, None, None]:
        """Fetch all pages and yield only users that are new or have changed since the last run.

        Every seen user (new or unchanged) is recorded in ``_current_run`` so that
        ``update_checkpoint`` can persist the full snapshot at the end of the run.
        """
        known = self._known_users

        for user in self._fetch_all_pages():
            # Always track the user in the current-run snapshot
            if user.id:
                self._current_run[user.id] = self._user_timestamp(user) or ""

            if self._is_new_or_changed(user, known):
                yield user

    def update_checkpoint(self) -> None:
        """Persist the full id→timestamp snapshot from the current run."""
        if self._current_run:
            with self.context as cache:
                cache[_CACHE_KEY] = self._current_run
            self.log(
                f"Checkpoint updated – {len(self._current_run)} users cached",
                level="debug",
            )
        else:
            self.log("No checkpoint update needed – no users seen this run", level="debug")

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        """Main entry point: yield new/changed Sophos directory users as OCSF models."""
        self.log("Starting Sophos user asset collection", level="info")
        total = 0
        skipped = 0

        try:
            for user in self._iter_users():
                mapped = self.map_user_fields(user)
                if mapped is not None:
                    total += 1
                    yield mapped
                else:
                    skipped += 1
        except Exception as exc:
            self.log(f"Asset collection failed – collected={total}, skipped={skipped}, error={exc}", level="error")
            raise

        self.log(f"Sophos user asset collection complete – total={total}, skipped={skipped}", level="info")
