import hashlib
from collections.abc import Generator
from functools import cached_property
from typing import Any

from google.auth.exceptions import RefreshError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from pydantic import ValidationError
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.connector import AssetList, DefaultAssetConnectorConfiguration
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.asset_connector.models.ocsf.user import UserOCSFModel
from sekoia_automation.storage import PersistentJSON

from google_module.asset_connector.mappers import UserMapper
from google_module.asset_connector.models import DirectoryGroup, DirectoryMember, DirectoryUser

KNOWN_USERS_KEY = "known_users"
# Key of the groups whose member is the whole customer, i.e. every user
EVERY_USER = "*"
# Retries of 429, 5xx and rate limit 403 answers, with exponential backoff
NUM_RETRIES = 5
RATE_LIMIT_REASONS = {"userRateLimitExceeded", "rateLimitExceeded"}
USER_SCOPE = "https://www.googleapis.com/auth/admin.directory.user.readonly"
GROUP_SCOPE = "https://www.googleapis.com/auth/admin.directory.group.readonly"
ACCESS_HINT = (
    "In the Admin console, under Security > API controls > Domain-wide delegation, authorize the service account "
    f"client ID for {USER_SCOPE} and {GROUP_SCOPE}, and set admin_mail to a Google Workspace administrator"
)


def is_access_denied(error: Exception) -> bool:
    """True for a missing delegation scope or administrator privilege, False for a transient error."""
    if isinstance(error, RefreshError):
        return not error.retryable
    if isinstance(error, HttpError) and error.status_code in (401, 403):
        reasons = {detail.get("reason") for detail in error.error_details or [] if isinstance(detail, dict)}
        return not reasons & RATE_LIMIT_REASONS
    return False


def unique_groups(groups: list[Group]) -> list[Group]:
    """Drop repeated groups by uid, keeping the first occurrence."""
    seen: set[str | None] = set()
    unique = []
    for group in groups:
        if group.uid not in seen:
            seen.add(group.uid)
            unique.append(group)
    return unique


class GoogleWorkspaceUserAssetConnectorConfiguration(DefaultAssetConnectorConfiguration):
    admin_mail: str


class GoogleWorkspaceUserAssetConnector(AssetConnector):
    """
    Collect Google Workspace users from the Admin SDK Directory API.

    The Directory API exposes no modification date and cannot filter users on any date.
    Every cycle lists all users and yields only those whose OCSF output changed since
    the previous cycle, tracked as a fingerprint per user id in `user_context.json`.
    """

    configuration: GoogleWorkspaceUserAssetConnectorConfiguration

    CUSTOMER = "my_customer"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("user_context.json", self._data_path)
        self._fingerprints: dict[str, str] = {}
        self._listing_complete = False
        self._pending = False

    def _build_directory(self, scope: str) -> Any:
        credentials = service_account.Credentials.from_service_account_info(
            self.module.configuration["credentials"], scopes=[scope]
        )
        return build(
            "admin",
            "directory_v1",
            credentials=credentials.with_subject(self.configuration.admin_mail),
            cache_discovery=False,
        )

    @cached_property
    def directory(self) -> Any:
        """Directory API client for users, acting as the configured Google Workspace administrator."""
        return self._build_directory(USER_SCOPE)

    @cached_property
    def groups_directory(self) -> Any:
        """Directory API client for groups, with its own scope so a missing group scope does not block users."""
        return self._build_directory(GROUP_SCOPE)

    def _list(self, resource: Any, key: str, **params: Any) -> Generator[dict[str, Any], None, None]:
        page_token = None
        while self.running:
            response = resource.list(pageToken=page_token, **params).execute(num_retries=NUM_RETRIES)
            yield from response.get(key, [])
            page_token = response.get("nextPageToken")
            if not page_token:
                return

    def _groups_by_user(self) -> dict[str, list[Group]]:
        """Return the groups each user is a direct member of, groups of every user under `EVERY_USER`."""
        groups_by_user: dict[str, list[Group]] = {}
        directory = self.groups_directory
        for raw_group in self._list(directory.groups(), "groups", customer=self.CUSTOMER, maxResults=200):
            try:
                group = DirectoryGroup.model_validate(raw_group)
            except ValidationError as error:
                self.log(f"Skipping Google Workspace group {raw_group.get('id')}: {error!r}", level="warning")
                continue
            if group.directMembersCount == "0":
                continue
            ocsf_group = Group(uid=group.id, name=group.name or group.email, desc=group.description or None)
            try:
                for raw_member in self._list(directory.members(), "members", groupKey=group.id, maxResults=200):
                    member = DirectoryMember.model_validate(raw_member)
                    if member.type == "USER" and member.id:
                        groups_by_user.setdefault(member.id, []).append(ocsf_group)
                    elif member.type == "CUSTOMER":
                        groups_by_user.setdefault(EVERY_USER, []).append(ocsf_group)
            except HttpError as error:
                # Group deleted between groups.list and members.list, or a group the administrator cannot read
                if error.status_code == 404:
                    reason = "not found"
                elif is_access_denied(error):
                    reason = "access denied"
                else:
                    raise
                self.log(f"Skipping Google Workspace group {group.id}: {reason}", level="warning")
        return groups_by_user

    def _groups_or_none(self) -> dict[str, list[Group]]:
        """Groups by user, empty when access to groups is denied so users are still collected."""
        try:
            return self._groups_by_user()
        except Exception as error:
            if not is_access_denied(error):
                raise
            self.log(f"Collecting users without groups, groups access denied: {error!r}. {ACCESS_HINT}", level="error")
            return {}

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        """Yield the users that are new or changed since the previous cycle."""
        with self.context as cache:
            known: dict[str, str] = cache.get(KNOWN_USERS_KEY, {})
        self._fingerprints = {}
        self._listing_complete = False
        self._pending = False
        changed = 0
        skipped = 0

        try:
            groups_by_user = self._groups_or_none()
            every_user_groups = groups_by_user.get(EVERY_USER, [])
            for raw_user in self._list(self.directory.users(), "users", customer=self.CUSTOMER, maxResults=500):
                try:
                    user = DirectoryUser.model_validate(raw_user)
                    groups = unique_groups(groups_by_user.get(user.id, []) + every_user_groups)
                    asset = UserMapper(user, groups).map()
                except Exception as error:
                    skipped += 1
                    self.log(f"Skipping Google Workspace user {raw_user.get('id')}: {error!r}", level="warning")
                    continue

                fingerprint = hashlib.sha256(asset.model_dump_json(exclude_none=True).encode()).hexdigest()[:16]
                # Set before the yield: the SDK checkpoints a full batch before resuming the generator
                self._fingerprints[user.id] = fingerprint
                if known.get(user.id) != fingerprint:
                    changed += 1
                    self._pending = True
                    yield asset
            self._listing_complete = self.running
        # Logged, not re-raised: the SDK run() would restart the cycle immediately, with no backoff.
        # The checkpoint stays in merge mode since _listing_complete is still False.
        except Exception as error:
            if is_access_denied(error):
                self.log(f"Google Workspace users access denied: {error!r}. {ACCESS_HINT}", level="error")
            else:
                self.log_exception(error, message="Failed to list Google Workspace users")

        # No push follows when every yielded user was already checkpointed: save the snapshot here
        if self._listing_complete and not self._pending:
            self.update_checkpoint()
        self.log(
            f"{changed} new or changed users, {skipped} skipped, out of {len(self._fingerprints)} listed",
            level="info",
        )

    def post_assets_to_api(self, assets: AssetList, asset_connector_api_url: str) -> dict[str, str] | None:
        """Push a batch; on failure forget its fingerprints so a later checkpoint does not mark its users known."""
        response = super().post_assets_to_api(assets, asset_connector_api_url)
        if response is None:
            for asset in assets.items:
                self._fingerprints.pop(asset.user.uid, None)  # type: ignore[union-attr]
        return response

    def update_checkpoint(self) -> None:
        """Save the fingerprints of the users listed so far."""
        with self.context as cache:
            # Once every user was listed, the snapshot replaces the cache and drops deleted users
            known = {} if self._listing_complete else cache.get(KNOWN_USERS_KEY, {})
            cache[KNOWN_USERS_KEY] = {**known, **self._fingerprints}
        self._pending = False

    def reset_checkpoint(self) -> None:
        """Forget every fingerprint so the next cycle pushes all users."""
        with self.context as cache:
            cache.pop(KNOWN_USERS_KEY, None)
        self._fingerprints = {}
        self._listing_complete = False
        self._pending = False
        self.log("Google Workspace users checkpoint reset", level="info")

    def get_mapped_fields(self) -> dict[str, str]:
        """Return the Directory API -> OCSF field mapping used for schema-change fingerprinting."""
        return {
            "creationTime": "time",
            "id": "user.uid, user.account.uid",
            "primaryEmail": "user.name, user.email_addr, user.domain, user.account.name",
            "name.fullName": "user.full_name",
            "name.displayName": "user.display_name",
            "isEnrolledIn2Sv": "user.has_mfa",
            "isAdmin": "user.type",
            "isDelegatedAdmin": "user.type",
            "members.list.id": "user.groups",
            "organizations.name": "user.org.name",
            "orgUnitPath": "user.org.ou_name",
            "name.givenName": "user.ldap_person.given_name",
            "name.familyName": "user.ldap_person.surname",
            "organizations.title": "user.ldap_person.job_title",
            "organizations.department": "user.ldap_person.department",
            "organizations.location": "user.ldap_person.office_location",
            "externalIds.value": "user.ldap_person.employee_uid",
            "suspended": "enrichments.access_control.data.is_enabled",
            "archived": "enrichments.access_control.data.is_enabled",
            "lastLoginTime": "enrichments.access_control.data.last_logon",
        }
