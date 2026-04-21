"""Pydantic models for Microsoft Entra ID API responses (typing only)."""

from datetime import datetime
from typing import Any, Optional, Union

from pydantic.v1 import BaseModel


class ObjectIdentity(BaseModel):
    issuer: Optional[str] = None
    issuer_assigned_id: Optional[str] = None
    odata_type: Optional[str] = None
    sign_in_type: Optional[str] = None
    additional_data: Optional[dict[str, Any]] = None


class SignInActivity(BaseModel):
    additional_data: Optional[dict[str, Any]] = None
    last_non_interactive_sign_in_date_time: Optional[datetime] = None
    last_non_interactive_sign_in_request_id: Optional[str] = None
    last_sign_in_date_time: Optional[datetime] = None
    last_sign_in_request_id: Optional[str] = None
    last_successful_sign_in_date_time: Optional[datetime] = None
    last_successful_sign_in_request_id: Optional[str] = None
    odata_type: Optional[str] = None


class PasswordAuthenticationMethod(BaseModel):
    additional_data: Optional[dict[str, Any]] = None
    id: Optional[str] = None
    odata_type: Optional[str] = None
    created_date_time: Optional[datetime] = None
    password: Optional[str] = None


class AuthenticationMethodCollectionResponse(BaseModel):
    additional_data: Optional[dict[str, Any]] = None
    odata_count: Optional[int] = None
    odata_next_link: Optional[str] = None
    value: Optional[list[PasswordAuthenticationMethod]] = None


class User(BaseModel):
    id: str
    additional_data: Optional[dict[str, Any]] = None
    odata_type: Optional[str] = None
    deleted_date_time: Optional[datetime] = None
    about_me: Optional[str] = None
    account_enabled: Optional[bool] = None
    activities: Optional[list[Any]] = None
    adhoc_calls: Optional[list[Any]] = None
    age_group: Optional[str] = None
    agreement_acceptances: Optional[list[Any]] = None
    app_role_assignments: Optional[list[Any]] = None
    assigned_licenses: Optional[list[Any]] = None
    assigned_plans: Optional[list[Any]] = None
    authentication: Optional[Any] = None
    authorization_info: Optional[Any] = None
    birthday: Optional[datetime] = None
    business_phones: Optional[list[str]] = None
    calendar: Optional[Any] = None
    calendar_groups: Optional[Any] = None
    calendar_view: Optional[Any] = None
    calendars: Optional[Any] = None
    chats: Optional[list[Any]] = None
    city: Optional[str] = None
    cloud_clipboard: Optional[Any] = None
    cloud_p_cs: Optional[Any] = None
    company_name: Optional[str] = None
    consent_provided_for_minor: Optional[str] = None
    contact_folders: Optional[Any] = None
    contacts: Optional[Any] = None
    country: Optional[str] = None
    created_date_time: Optional[datetime] = None
    created_objects: Optional[Any] = None
    creation_type: Optional[str] = None
    custom_security_attributes: Optional[Any] = None
    data_security_and_governance: Optional[Any] = None
    department: Optional[str] = None
    device_enrollment_limit: Optional[int] = None
    device_management_troubleshooting_events: Optional[Any] = None
    direct_reports: Optional[Any] = None
    display_name: Optional[str] = None
    drive: Optional[Any] = None
    drives: Optional[Any] = None
    employee_experience: Optional[Any] = None
    employee_hire_date: Optional[datetime] = None
    employee_id: Optional[str] = None
    employee_leave_date_time: Optional[datetime] = None
    employee_org_data: Optional[Any] = None
    employee_type: Optional[str] = None
    events: Optional[Any] = None
    extensions: Optional[Any] = None
    external_user_state: Optional[str] = None
    external_user_state_change_date_time: Optional[datetime] = None
    fax_number: Optional[str] = None
    followed_sites: Optional[Any] = None
    given_name: Optional[str] = None
    hire_date: Optional[datetime] = None
    identities: Optional[list[ObjectIdentity]] = None
    im_addresses: Optional[list[str]] = None
    inference_classification: Optional[Any] = None
    insights: Optional[Any] = None
    interests: Optional[list[str]] = None
    is_management_restricted: Optional[bool] = None
    is_resource_account: Optional[bool] = None
    job_title: Optional[str] = None
    joined_teams: Optional[Any] = None
    last_password_change_date_time: Optional[datetime] = None
    legal_age_group_classification: Optional[str] = None
    license_assignment_states: Optional[Any] = None
    license_details: Optional[Any] = None
    mail: Optional[str] = None
    mail_folders: Optional[Any] = None
    mail_nickname: Optional[str] = None
    mailbox_settings: Optional[Any] = None
    managed_app_registrations: Optional[Any] = None
    managed_devices: Optional[Any] = None
    manager: Optional[Any] = None
    member_of: Optional[Any] = None
    messages: Optional[Any] = None
    mobile_phone: Optional[str] = None
    my_site: Optional[Any] = None
    oauth2_permission_grants: Optional[Any] = None
    office_location: Optional[str] = None
    on_premises_distinguished_name: Optional[str] = None
    on_premises_domain_name: Optional[str] = None
    on_premises_extension_attributes: Optional[Any] = None
    on_premises_immutable_id: Optional[str] = None
    on_premises_last_sync_date_time: Optional[datetime] = None
    on_premises_provisioning_errors: Optional[Any] = None
    on_premises_sam_account_name: Optional[str] = None
    on_premises_security_identifier: Optional[str] = None
    on_premises_sync_behavior: Optional[str] = None
    on_premises_sync_enabled: Optional[bool] = None
    on_premises_user_principal_name: Optional[str] = None
    onenote: Optional[Any] = None
    online_meetings: Optional[Any] = None
    other_mails: Optional[list[str]] = None
    outlook: Optional[Any] = None
    owned_devices: Optional[Any] = None
    owned_objects: Optional[Any] = None
    password_policies: Optional[str] = None
    password_profile: Optional[Any] = None
    past_projects: Optional[list[str]] = None
    people: Optional[Any] = None
    permission_grants: Optional[Any] = None
    photo: Optional[Any] = None
    photos: Optional[Any] = None
    planner: Optional[Any] = None
    postal_code: Optional[str] = None
    preferred_data_location: Optional[str] = None
    preferred_language: Optional[str] = None
    preferred_name: Optional[str] = None
    presence: Optional[Any] = None
    print: Optional[Any] = None
    provisioned_plans: Optional[Any] = None
    proxy_addresses: Optional[list[str]] = None
    registered_devices: Optional[Any] = None
    responsibilities: Optional[list[str]] = None
    schools: Optional[list[Any]] = None
    scoped_role_member_of: Optional[Any] = None
    security_identifier: Optional[str] = None
    service_provisioning_errors: Optional[Any] = None
    settings: Optional[Any] = None
    show_in_address_list: Optional[bool] = None
    sign_in_activity: Optional[SignInActivity] = None
    sign_in_sessions_valid_from_date_time: Optional[datetime] = None
    skills: Optional[list[str]] = None
    solutions: Optional[list[str]] = None
    sponsors: Optional[Any] = None
    state: Optional[str] = None
    street_address: Optional[str] = None
    surname: Optional[str] = None
    teamwork: Optional[Any] = None
    todo: Optional[Any] = None
    transitive_member_of: Optional[Any] = None
    usage_location: Optional[str] = None
    user_principal_name: Optional[str] = None
    user_type: Optional[str] = None


class UserCollectionResponse(BaseModel):
    additional_data: Optional[dict[str, Any]] = None
    odata_count: Optional[int] = None
    odata_next_link: Optional[str] = None
    value: Optional[list[User]] = None


class DirectoryRole(BaseModel):
    additional_data: Optional[dict[str, Any]] = None
    id: Optional[str] = None
    odata_type: Optional[str] = None
    deleted_date_time: Optional[datetime] = None
    description: Optional[str] = None
    display_name: Optional[str] = None
    members: Optional[list[Any]] = None
    role_template_id: Optional[str] = None
    scoped_members: Optional[list[Any]] = None


class DirectoryRoleCollectionResponse(BaseModel):
    additional_data: Optional[dict[str, Any]] = None
    odata_count: Optional[int] = None
    odata_next_link: Optional[str] = None
    value: Optional[list[DirectoryRole]] = None


class Group(BaseModel):
    additional_data: Optional[dict[str, Any]] = None
    id: Optional[str] = None
    odata_type: Optional[str] = None
    deleted_date_time: Optional[datetime] = None
    description: Optional[str] = None
    display_name: Optional[str] = None
    created_date_time: Optional[datetime] = None
    renewed_date_time: Optional[datetime] = None
    expiration_date_time: Optional[datetime] = None
    group_types: Optional[list[str]] = None
    membership_rule: Optional[str] = None
    membership_rule_processing_state: Optional[str] = None
    mail: Optional[str] = None
    mail_enabled: Optional[bool] = None
    mail_nickname: Optional[str] = None
    security_enabled: Optional[bool] = None
    security_identifier: Optional[str] = None
    visibility: Optional[str] = None
    is_archived: Optional[bool] = None
    is_assignable_to_role: Optional[bool] = None
    is_management_restricted: Optional[bool] = None
    is_subscribed_by_mail: Optional[bool] = None
    preferred_data_location: Optional[str] = None
    preferred_language: Optional[str] = None
    unique_name: Optional[str] = None
    unseen_count: Optional[int] = None
    classification: Optional[str] = None
    accepted_senders: Optional[list[Any]] = None
    rejected_senders: Optional[list[Any]] = None
    allow_external_senders: Optional[bool] = None
    auto_subscribe_new_members: Optional[bool] = None
    app_role_assignments: Optional[list[Any]] = None
    assigned_labels: Optional[list[Any]] = None
    assigned_licenses: Optional[list[Any]] = None
    members: Optional[list[Any]] = None
    member_of: Optional[list[Any]] = None
    members_with_license_errors: Optional[list[Any]] = None
    has_members_with_license_errors: Optional[bool] = None
    transitive_member_of: Optional[list[Any]] = None
    transitive_members: Optional[list[Any]] = None
    owners: Optional[list[Any]] = None
    permission_grants: Optional[list[Any]] = None
    settings: Optional[list[Any]] = None
    service_provisioning_errors: Optional[list[Any]] = None
    on_premises_domain_name: Optional[str] = None
    on_premises_net_bios_name: Optional[str] = None
    on_premises_sam_account_name: Optional[str] = None
    on_premises_security_identifier: Optional[str] = None
    on_premises_sync_behavior: Optional[str] = None
    on_premises_sync_enabled: Optional[bool] = None
    on_premises_last_sync_date_time: Optional[datetime] = None
    on_premises_provisioning_errors: Optional[list[Any]] = None
    resource_behavior_options: Optional[list[str]] = None
    resource_provisioning_options: Optional[list[str]] = None
    license_processing_state: Optional[Any] = None
    calendar: Optional[Any] = None
    calendar_view: Optional[Any] = None
    conversations: Optional[Any] = None
    drive: Optional[Any] = None
    drives: Optional[Any] = None
    events: Optional[Any] = None
    extensions: Optional[list[Any]] = None
    group_lifecycle_policies: Optional[list[Any]] = None
    onenote: Optional[Any] = None
    photo: Optional[Any] = None
    photos: Optional[Any] = None
    planner: Optional[Any] = None
    sites: Optional[Any] = None
    team: Optional[Any] = None
    theme: Optional[str] = None
    threads: Optional[Any] = None
    created_on_behalf_of: Optional[Any] = None


class DirectoryObjectCollectionResponse(BaseModel):
    additional_data: Optional[dict[str, Any]] = None
    odata_count: Optional[int] = None
    odata_next_link: Optional[str] = None
    value: Optional[list[Union[DirectoryRole, Group]]] = None

