import hashlib
from collections.abc import Generator
from functools import cached_property
from typing import Any

from dateutil.parser import isoparse
from google.auth.exceptions import RefreshError
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.connector import AssetList, DefaultAssetConnectorConfiguration
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.asset_connector.models.ocsf.organization import Organization
from sekoia_automation.asset_connector.models.ocsf.user import (
    Account,
    AccountTypeId,
    AccountTypeStr,
    LdapPerson,
    User,
    UserDataObject,
    UserEnrichmentObject,
    UserOCSFModel,
    UserTypeId,
    UserTypeStr,
)
from sekoia_automation.storage import PersistentJSON

KNOWN_USERS_KEY = "known_users"
# Directory API value of lastLoginTime for a user who never logged in
NEVER_LOGGED_IN_PREFIX = "1970-01-01"
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
    OCSF_VERSION = "1.6.0"

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
        for group in self._list(directory.groups(), "groups", customer=self.CUSTOMER, maxResults=200):
            if group.get("directMembersCount") == "0":
                continue
            ocsf_group = Group(
                uid=group["id"], name=group.get("name") or group["email"], desc=group.get("description") or None
            )
            try:
                for member in self._list(directory.members(), "members", groupKey=group["id"], maxResults=200):
                    if member.get("type") == "USER":
                        groups_by_user.setdefault(member["id"], []).append(ocsf_group)
                    elif member.get("type") == "CUSTOMER":
                        groups_by_user.setdefault(EVERY_USER, []).append(ocsf_group)
            except HttpError as error:
                # Group deleted between groups.list and members.list
                if error.status_code != 404:
                    raise
                self.log(f"Skipping Google Workspace group {group['id']}: not found", level="warning")
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

    def map_fields(self, user: dict[str, Any], groups: list[Group]) -> UserOCSFModel:
        """Map a Directory API user and its groups to the OCSF user inventory model."""
        email = user["primaryEmail"]
        domain = email.split("@")[-1]
        name = user.get("name") or {}
        organizations = user.get("organizations") or []
        organization = next(
            (org for org in organizations if org.get("primary")), organizations[0] if organizations else {}
        )
        employee_uid = next(
            (
                external.get("value")
                for external in user.get("externalIds") or []
                if external.get("type") == "organization"
            ),
            None,
        )
        is_admin = user.get("isAdmin") or user.get("isDelegatedAdmin")
        last_login = user.get("lastLoginTime")

        return UserOCSFModel(
            activity_id=2,
            activity_name="Collect",
            category_name="Discovery",
            category_uid=5,
            class_name="User Inventory Info",
            class_uid=5003,
            type_name="User Inventory Info: Collect",
            type_uid=500302,
            severity="Informational",
            severity_id=1,
            time=isoparse(user["creationTime"]).timestamp(),
            metadata=Metadata(
                product=Product(name="Google Workspace", vendor_name="Google", version="N/A"),
                version=self.OCSF_VERSION,
            ),
            user=User(
                uid=user["id"],
                name=email,
                email_addr=email,
                full_name=name.get("fullName"),
                display_name=name.get("displayName"),
                domain=domain,
                has_mfa=user.get("isEnrolledIn2Sv"),
                type_id=UserTypeId.ADMIN if is_admin else UserTypeId.USER,
                type=UserTypeStr.ADMIN if is_admin else UserTypeStr.USER,
                account=Account(
                    name=email,
                    uid=user["id"],
                    type_id=AccountTypeId.GOOGLE_WORKSPACE,
                    type=AccountTypeStr.GOOGLE_WORKSPACE,
                ),
                groups=sorted(groups, key=lambda group: group.uid or "") or None,
                org=Organization(name=organization.get("name") or domain, ou_name=user.get("orgUnitPath")),
                ldap_person=LdapPerson(
                    given_name=name.get("givenName"),
                    surname=name.get("familyName"),
                    job_title=organization.get("title"),
                    department=organization.get("department"),
                    office_location=organization.get("location"),
                    employee_uid=employee_uid,
                ),
            ),
            enrichments=[
                UserEnrichmentObject(
                    name="access_control",
                    value="google_workspace",
                    data=UserDataObject(
                        is_enabled=not (user.get("suspended") or user.get("archived")),
                        last_logon=(
                            last_login if last_login and not last_login.startswith(NEVER_LOGGED_IN_PREFIX) else None
                        ),
                    ),
                )
            ],
        )

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        """Yield the users that are new or changed since the previous cycle."""
        with self.context as cache:
            known: dict[str, str] = cache.get(KNOWN_USERS_KEY, {})
        self._fingerprints = {}
        self._listing_complete = False
        self._pending = False
        changed = 0

        try:
            groups_by_user = self._groups_or_none()
            every_user_groups = groups_by_user.get(EVERY_USER, [])
            for user in self._list(self.directory.users(), "users", customer=self.CUSTOMER, maxResults=500):
                try:
                    asset = self.map_fields(user, groups_by_user.get(user["id"], []) + every_user_groups)
                except Exception as error:
                    self.log(f"Skipping Google Workspace user {user.get('id')}: {error!r}", level="warning")
                    continue

                fingerprint = hashlib.sha256(asset.model_dump_json().encode()).hexdigest()[:16]
                # Set before the yield: the SDK checkpoints a full batch before resuming the generator
                self._fingerprints[user["id"]] = fingerprint
                if known.get(user["id"]) != fingerprint:
                    changed += 1
                    self._pending = True
                    yield asset
            self._listing_complete = self.running
        except Exception as error:
            if is_access_denied(error):
                self.log(f"Google Workspace users access denied: {error!r}. {ACCESS_HINT}", level="error")
            else:
                self.log_exception(error, message="Failed to list Google Workspace users")

        # No push follows when every yielded user was already checkpointed: save the snapshot here
        if self._listing_complete and not self._pending:
            self.update_checkpoint()
        self.log(f"{changed} new or changed users out of {len(self._fingerprints)} listed", level="info")

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
