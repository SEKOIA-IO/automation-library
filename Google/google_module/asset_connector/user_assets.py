import hashlib
from collections.abc import Generator
from functools import cached_property
from typing import Any

from dateutil.parser import isoparse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.connector import DefaultAssetConnectorConfiguration
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

    SCOPES = [
        "https://www.googleapis.com/auth/admin.directory.user.readonly",
        "https://www.googleapis.com/auth/admin.directory.group.readonly",
    ]
    CUSTOMER = "my_customer"
    OCSF_VERSION = "1.6.0"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("user_context.json", self._data_path)
        self._fingerprints: dict[str, str] = {}
        self._listing_complete = False
        self._pending = False

    @cached_property
    def directory(self) -> Any:
        """Directory API client acting as the configured Google Workspace administrator."""
        credentials = service_account.Credentials.from_service_account_info(
            self.module.configuration["credentials"], scopes=self.SCOPES
        )
        return build(
            "admin",
            "directory_v1",
            credentials=credentials.with_subject(self.configuration.admin_mail),
            cache_discovery=False,
        )

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
        for group in self._list(self.directory.groups(), "groups", customer=self.CUSTOMER, maxResults=200):
            ocsf_group = Group(
                uid=group["id"], name=group.get("name") or group["email"], desc=group.get("description") or None
            )
            for member in self._list(self.directory.members(), "members", groupKey=group["id"], maxResults=200):
                if member.get("type") == "USER":
                    groups_by_user.setdefault(member["id"], []).append(ocsf_group)
                elif member.get("type") == "CUSTOMER":
                    groups_by_user.setdefault(EVERY_USER, []).append(ocsf_group)
        return groups_by_user

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
            groups_by_user = self._groups_by_user()
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
            self.log_exception(error, message="Failed to list Google Workspace users")

        # No push follows when every yielded user was already checkpointed: save the snapshot here
        if self._listing_complete and not self._pending:
            self.update_checkpoint()
        self.log(f"{changed} new or changed users out of {len(self._fingerprints)} listed", level="info")

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
        """Empty: fingerprints cover the OCSF output, so a mapping change re-pushes affected users on its own."""
        return {}
