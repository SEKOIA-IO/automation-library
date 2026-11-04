from dateutil.parser import isoparse
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

from google_module.asset_connector.models import DirectoryUser, UserName, UserOrganization

# Directory API value of lastLoginTime for a user who never logged in
NEVER_LOGGED_IN_PREFIX = "1970-01-01"


class UserMapper:
    """Map one Directory API user and its groups to the OCSF User Inventory Info model."""

    OCSF_VERSION = "1.6.0"

    def __init__(self, user: DirectoryUser, groups: list[Group]) -> None:
        self.user = user
        self.groups = groups

    @property
    def organization(self) -> UserOrganization:
        """The primary organization, else the first one, else an empty one."""
        organizations = self.user.organizations or []
        return next(
            (org for org in organizations if org.primary), organizations[0] if organizations else UserOrganization()
        )

    @property
    def employee_uid(self) -> str | None:
        return next(
            (external.value for external in self.user.externalIds or [] if external.type == "organization"), None
        )

    @property
    def last_logon(self) -> str | None:
        last_login = self.user.lastLoginTime
        return last_login if last_login and not last_login.startswith(NEVER_LOGGED_IN_PREFIX) else None

    def map(self) -> UserOCSFModel:
        user = self.user
        email = user.primaryEmail
        domain = email.split("@")[-1]
        name = user.name or UserName()
        organization = self.organization
        is_admin = user.isAdmin or user.isDelegatedAdmin

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
            time=isoparse(user.creationTime).timestamp(),
            metadata=Metadata(
                product=Product(name="Google Workspace", vendor_name="Google", version="N/A"),
                version=self.OCSF_VERSION,
            ),
            user=User(
                uid=user.id,
                name=email,
                email_addr=email,
                full_name=name.fullName,
                display_name=name.displayName,
                domain=domain,
                has_mfa=user.isEnrolledIn2Sv,
                type_id=UserTypeId.ADMIN if is_admin else UserTypeId.USER,
                type=UserTypeStr.ADMIN if is_admin else UserTypeStr.USER,
                account=Account(
                    name=email,
                    uid=user.id,
                    type_id=AccountTypeId.GOOGLE_WORKSPACE,
                    type=AccountTypeStr.GOOGLE_WORKSPACE,
                ),
                groups=sorted(self.groups, key=lambda group: group.uid or "") or None,
                org=Organization(name=organization.name or domain, ou_name=user.orgUnitPath),
                ldap_person=LdapPerson(
                    given_name=name.givenName,
                    surname=name.familyName,
                    job_title=organization.title,
                    department=organization.department,
                    office_location=organization.location,
                    employee_uid=self.employee_uid,
                ),
            ),
            enrichments=[
                UserEnrichmentObject(
                    name="access_control",
                    value="google_workspace",
                    data=UserDataObject(
                        is_enabled=not (user.suspended or user.archived),
                        last_logon=self.last_logon,
                    ),
                )
            ],
        )
