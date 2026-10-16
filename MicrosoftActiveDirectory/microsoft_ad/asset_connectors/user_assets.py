import datetime
from collections.abc import Generator
from typing import Any

from ldap3 import ALL_ATTRIBUTES, ALL_OPERATIONAL_ATTRIBUTES
from ldap3.core.exceptions import LDAPException
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.group import Group
from sekoia_automation.asset_connector.models.ocsf.user import (
    Account,
    AccountTypeId,
    AccountTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.user import User as UserOCSF
from sekoia_automation.asset_connector.models.ocsf.user import (
    UserDataObject,
    UserEnrichmentObject,
    UserOCSFModel,
    UserTypeId,
    UserTypeStr,
)
from sekoia_automation.storage import PersistentJSON

from microsoft_ad.client.ldap_client import LDAPClient
from microsoft_ad.models.common_models import LDAPUserAttributes, MicrosoftADConnectorConfiguration, MicrosoftADModule


class MicrosoftADUserAssetConnector(AssetConnector, LDAPClient):
    module: MicrosoftADModule
    configuration: MicrosoftADConnectorConfiguration

    PRODUCT_NAME: str = "Microsoft Active Directory"
    VENDOR_NAME: str = "Microsoft"
    PRODUCT_VERSION = "N/A"
    LIMIT: int = 100
    QUERY_ATTRIBUTES: list[str] = [ALL_ATTRIBUTES, ALL_OPERATIONAL_ATTRIBUTES]

    # OCSF Constants
    OCSF_ACTIVITY_ID = 2
    OCSF_ACTIVITY_NAME = "Collect"
    OCSF_CATEGORY_UID = 5
    OCSF_CATEGORY_NAME = "Collect"
    OCSF_CLASS_UID = 5003
    OCSF_CLASS_NAME = "User Inventory Info"
    OCSF_TYPE_UID = 500302
    OCSF_TYPE_NAME = "User Inventory"
    OCSF_SEVERITY = "Informational"
    OCSF_SEVERITY_ID = 1

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self._latest_time: str | None = None
        self._seen_sids: set[str] = set()

    @property
    def most_recent_datetime(self) -> str | None:
        with self.context as cache:
            return cache.get("most_recent_datetime", None)

    @property
    def seen_sids_at_checkpoint(self) -> set[str]:
        with self.context as cache:
            return set(cache.get("seen_sids_at_checkpoint", []))

    @property
    def user_ldap_query(self) -> str:
        if not self.most_recent_datetime:
            return "(&(objectCategory=person)(objectClass=user))"
        return f"(&(objectCategory=person)(objectClass=user)(whenCreated>={self.most_recent_datetime}))"

    def update_checkpoint(self) -> None:
        if self._latest_time is None:
            return

        with self.context as cache:
            previous_checkpoint = cache.get("most_recent_datetime")

            if self._latest_time == previous_checkpoint:
                existing_sids = set(cache.get("seen_sids_at_checkpoint", []))
                cache["seen_sids_at_checkpoint"] = list(existing_sids | self._seen_sids)
            else:
                cache["most_recent_datetime"] = self._latest_time
                cache["seen_sids_at_checkpoint"] = list(self._seen_sids)

    def user_metadata_object(self) -> Metadata:
        """
        Create Metadata object for Microsoft AD product.
        :return:
            Metadata: Metadata object with product information.
        """
        product = Product(
            name=self.PRODUCT_NAME,
            vendor_name=self.VENDOR_NAME,
            version=self.PRODUCT_VERSION,
        )
        return Metadata(product=product, version="1.6.0")

    def compute_enabling_condition(self, user_attributes: LDAPUserAttributes) -> bool:
        """
        Compute if the user account is enabled based on userAccountControl attribute.
        :param
            user_attribute: LDAPUserAttributes: LDAP user attributes.
        :return:
            bool: True if the account is enabled, False otherwise.
        """
        user_account_control = user_attributes.userAccountControl or 0
        return not bool(user_account_control & 2)

    def convert_last_logon_to_timestamp(self, last_logon: datetime.datetime | None) -> str | None:
        """
        Convert lastLogon datetime to timestamp.
        :param
            last_logon: datetime.datetime | None: Last logon datetime from AD.
        :return:
            int | None: Timestamp in seconds or None if invalid.
        """
        # Check for invalid or unset lastLogon
        # In AD, a lastLogon value of 0 or a date before 1601 indicates no logon
        if not last_logon or last_logon.year <= 1601:
            return None
        return str(int(last_logon.timestamp()))

    def enrich_metadata(self, user_attributes: LDAPUserAttributes) -> list[UserEnrichmentObject]:
        """
        Enrich user metadata with additional information.
        :param
            user_attributes: LDAPUserAttributes: LDAP user attributes.
        :return:
            list[UserEnrichmentObject]: List of user enrichment objects.
        """
        pwd_last_set = user_attributes.pwdLastSet

        data = UserDataObject(
            is_enabled=self.compute_enabling_condition(user_attributes),
            last_logon=self.convert_last_logon_to_timestamp(user_attributes.lastLogon),
            bad_password_count=user_attributes.badPwdCount,
            number_of_logons=user_attributes.logonCount,
        )
        user_object = UserEnrichmentObject(name="login", value="infos", data=data)
        return [user_object]

    @staticmethod
    def _upn_local_part_ends_with_dollar(value: str) -> bool:
        """Return True if the local part (before '@') of an AD UPN-like string ends with '$'."""
        if "@" in value:
            return value.split("@", 1)[0].endswith("$")
        return False

    @staticmethod
    def is_machine_account(user_attributes: LDAPUserAttributes) -> bool:
        """Detect machine/computer accounts in AD."""
        if user_attributes.sAMAccountName and user_attributes.sAMAccountName.endswith("$"):
            return True
        upn = user_attributes.userPrincipalName
        if upn and MicrosoftADUserAssetConnector._upn_local_part_ends_with_dollar(upn):
            return True
        return False

    def compute_user_type(self, user_attributes: LDAPUserAttributes) -> tuple[UserTypeStr, UserTypeId]:
        """
        Compute user type based on LDAP user attributes.
        :param
            user_attributes: LDAPUserAttributes: LDAP user attributes.
        :return:
            tuple[UserTypeStr, UserTypeId]: User type string and ID.
        """
        if self.is_machine_account(user_attributes):
            return UserTypeStr.SYSTEM, UserTypeId.SYSTEM

        group_memberships = user_attributes.member_of or []
        for group_dn in group_memberships:
            if "admin" in group_dn.lower():
                return UserTypeStr.ADMIN, UserTypeId.ADMIN
        return UserTypeStr.USER, UserTypeId.USER

    def get_user_groups(self, user_attributes: LDAPUserAttributes) -> list[Group]:
        """
        Extract user groups from LDAP user attributes.
        :param
            user_attributes: LDAPUserAttributes: LDAP user attributes.
        :return:
            list[Group]: List of user groups.
        """
        group_memberships = user_attributes.member_of or []
        user_groups: list[Group] = []
        for group_dn in group_memberships:
            group_object = Group(
                name=group_dn,
            )
            user_groups.append(group_object)
        return user_groups

    @staticmethod
    def resolve_email_addr(mail: str | None) -> str | None:
        """
        Return the mail value only if it is a real email address.
        AD UPN-style values whose local part ends with '$'
        """
        if mail and "@" in mail and not MicrosoftADUserAssetConnector._upn_local_part_ends_with_dollar(mail):
            return mail
        return None

    def user_ocsf_object(self, user_attributes: LDAPUserAttributes) -> UserOCSF:
        """
        Build OCSF User object from LDAP user attributes.
        :param
            user_attributes: LDAPUserAttributes: LDAP user attributes.
        :return:
            UserOCSF: OCSF User object.
        """

        # Determine user type
        user_type, user_type_id = self.compute_user_type(user_attributes)

        # Build user name
        first_name = user_attributes.givenName
        last_name = user_attributes.sn

        if first_name and last_name:
            user_name = f"{first_name} {last_name}".strip()
        elif first_name:
            user_name = first_name.strip()
        elif last_name:
            user_name = last_name.strip()
        else:
            user_name = "Unknown"

        # Parse alternative UID
        if uid_alt := user_attributes.objectGUID:
            uid_alt = uid_alt.strip("{}")
        else:
            uid_alt = None

        # Build account object
        account = Account(
            name=user_attributes.userPrincipalName or "Unknown",
            type_id=AccountTypeId.LDAP_ACCOUNT,
            type=AccountTypeStr.LDAP_ACCOUNT,
            uid=user_attributes.objectSid or "Unknown",
        )

        email_addr = self.resolve_email_addr(user_attributes.mail)

        return UserOCSF(
            name=user_name,
            uid=user_attributes.objectSid or "Unknown",
            account=account,
            groups=self.get_user_groups(user_attributes),
            full_name=user_attributes.displayName or "Unknown",
            email_addr=email_addr,
            display_name=user_attributes.displayName or "Unknown",
            domain=user_attributes.distinguishedName or "Unknown",
            type_id=user_type_id,
            type=user_type,
            uid_alt=uid_alt,
        )

    def map_user_fields(self, user: dict[str, Any]) -> UserOCSFModel:
        """
        Map LDAP user attributes to OCSF User model.
        :param
            user: dict[str, Any]: LDAP user entry.
        :return:
            UserOCSFModel: Mapped OCSF User model.
        """
        raw_attributes = user.get("attributes", {})

        # Check if raw_attributes is not empty
        if not raw_attributes:
            self.log("No user attributes found for user", level="error")
            raise Exception("No user attributes found for user")

        user_attributes = LDAPUserAttributes(**raw_attributes)

        user_ocsf_model = UserOCSFModel(
            activity_id=self.OCSF_ACTIVITY_ID,
            activity_name=self.OCSF_ACTIVITY_NAME,
            category_name=self.OCSF_CATEGORY_NAME,
            category_uid=self.OCSF_CATEGORY_UID,
            class_name=self.OCSF_CLASS_NAME,
            class_uid=self.OCSF_CLASS_UID,
            type_uid=self.OCSF_TYPE_UID,
            severity=self.OCSF_SEVERITY,
            severity_id=self.OCSF_SEVERITY_ID,
            time=int(user_attributes.whenCreated.timestamp()) if user_attributes.whenCreated else 0,
            metadata=self.user_metadata_object(),
            user=self.user_ocsf_object(user_attributes),
            enrichments=self.enrich_metadata(user_attributes),
            type_name=self.OCSF_TYPE_NAME,
        )

        return user_ocsf_model

    def _run_paged_search(self) -> Generator[dict[str, Any], None, None]:
        return self.ldap_client.extend.standard.paged_search(
            search_base=self.configuration.basedn,
            search_filter=self.user_ldap_query,
            attributes=self.QUERY_ATTRIBUTES,
            paged_size=self.LIMIT,
            generator=True,
        )

    def _entries(self) -> Generator[dict[str, Any], None, None]:

        seen_dn: set[str] = set()

        for attempt in range(2):
            try:
                for entry in self._run_paged_search():
                    dn = entry.get("dn")
                    if dn is not None:
                        if dn in seen_dn:
                            continue
                        seen_dn.add(dn)
                    yield entry
                return
            except LDAPException as exc:
                if attempt == 1:
                    raise
                self.log(f"LDAP error, reconnecting... ({exc})", level="warning")
                self._reset_ldap_connection()

    def get_users_generator(self) -> Generator[dict[str, Any], None, None]:

        self.log("Starting LDAP paged search for users...", level="info")

        checkpoint_time = self.most_recent_datetime
        already_seen_sids = self.seen_sids_at_checkpoint

        for entry in self._entries():
            user_attributes = entry.get("attributes", {})
            if not user_attributes:
                self.log("No user attributes found for user", level="error")
                raise Exception("No user attributes found for user")

            user_created_at = user_attributes.get("whenCreated")
            if user_created_at:
                user_created_str = user_created_at.strftime("%Y%m%d%H%M%S.0Z")
                if user_created_str == checkpoint_time:
                    sid = user_attributes.get("objectSid")
                    if sid and sid in already_seen_sids:
                        self.log(
                            f"Skipping already-seen user (SID={sid}) at boundary second {checkpoint_time}",
                            level="debug",
                        )
                        continue

            self.log(f"User with DN {entry.get('dn')} retrieved.", level="debug")
            yield entry

            self.log(f"Start updating checkpoint with the new date {user_created_at}", level="debug")

            if user_created_at:
                user_created_str = user_created_at.strftime("%Y%m%d%H%M%S.0Z")
                sid = user_attributes.get("objectSid")
                if not self._latest_time or user_created_str > self._latest_time:
                    self._latest_time = user_created_str
                    self._seen_sids = {sid} if sid else set()
                elif user_created_str == self._latest_time and sid:
                    self._seen_sids.add(sid)

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        """
        Generate Microsoft AD user assets in OCSF format.

        Yields:
            Generator[UserOCSFModel]: An OCSF model representing a Microsoft AD user.
        """

        self.log("Start Microsoft AD user assets generator !!", level="info")
        self.log(f"Data path: {self._data_path.absolute()}", level="info")

        for user in self.get_users_generator():
            try:
                yield self.map_user_fields(user)
            except Exception as e:
                user_dn = user.get("dn", "Unknown DN")
                self.log(f"Failed to map user {user_dn}: {e}", level="error")
                continue
