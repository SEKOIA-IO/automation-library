"""Okta User Asset Connector module.

This module provides functionality to collect user assets from Okta
and format them according to OCSF standards.
"""

import asyncio
from collections.abc import AsyncGenerator
from functools import cached_property
from typing import Any, Optional

from dateutil.parser import isoparse
from okta.client import Client as OktaClient
from okta.models.user import User as OktaUser
from okta.models.role import Role as OktaRole
from okta.models.role_status import RoleStatus as OktaRoleStatus
from sekoia_automation.asset_connector import AsyncAssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.user import (
    Account,
    AccountTypeId,
    AccountTypeStr,
    Group,
    User,
    UserOCSFModel,
    UserTypeId,
    UserTypeStr,
)
from sekoia_automation.storage import PersistentJSON

from okta_modules import OktaModule


class OktaUserAssetConnector(AsyncAssetConnector):
    """Asset connector for collecting user data from Okta.

    This connector fetches user information from Okta and formats it
    according to OCSF (Open Cybersecurity Schema Framework) standards.
    """

    module: OktaModule

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the Okta User Asset Connector.

        Args:
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self.new_most_recent_date: Optional[str] = None

    @property
    def most_recent_date_seen(self) -> str | None:
        """Get the most recent date seen from the context cache.

        Returns:
            The most recent date seen as a string, or None if not set.
        """
        with self.context as cache:
            result: str | None = cache.get("most_recent_date_seen", None)

        return result

    def update_checkpoint(self) -> None:
        """Update the checkpoint with the most recent date seen.

        Raises:
            ValueError: If new_most_recent_date is None.
        """
        if self.new_most_recent_date is None:
            self.log("Warning: new_most_recent_date is None, skipping checkpoint update", level="warning")
            return

        try:
            with self.context as cache:
                cache["most_recent_date_seen"] = self.new_most_recent_date
                self.log(f"Checkpoint updated with date: {self.new_most_recent_date}", level="info")
        except Exception as e:
            self.log(f"Failed to update checkpoint: {str(e)}", level="warning")
            self.log_exception(e)

    @cached_property
    def client(self) -> OktaClient:
        """Get the Okta client instance.

        Returns:
            Configured OktaClient instance.
        """
        config = {
            "orgUrl": self.module.configuration.base_url,
            "token": self.module.configuration.apikey,
        }
        return OktaClient(config)

    async def get_group_privileges(self, group_id: str) -> list[str]:
        """Get privileges for a specific group.

        Args:
            group_id: The unique identifier of the group.
        Returns:
            List of privilege names associated with the group.
        """
        privileges, _, err = await self.client.list_group_assigned_roles(group_id)
        if err:
            self.log(f"Error while fetching privileges for group {group_id}: {err}", level="warning")
            return []

        if not privileges:
            self.log(f"No privileges found for group {group_id}", level="debug")
            return []

        privilege_names = []
        for privilege in privileges:
            if privilege.status == OktaRoleStatus.ACTIVE:
                privilege_names.append(privilege.label)

        return privilege_names

    async def get_user_groups(self, user_id: str) -> list[Group]:
        """Get all groups for a specific user.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            List of Group objects associated with the user.
        """
        groups, resp, err = await self.client.list_user_groups(user_id)
        if err:
            self.log(f"Error while fetching groups for user {user_id}: {err}", level="warning")
            return []

        if not groups:
            self.log(f"No groups found for user {user_id}", level="warning")
            return []

        # Use list comprehension for better performance
        group_list = [
            Group(
                name=group.profile.name,
                uid=group.id,
                desc=group.profile.description,
                privileges=await self.get_group_privileges(group.id),
            )
            for group in groups
        ]

        while resp.has_next():
            groups, resp, err = await resp.next()
            if err:
                self.log(f"Error while fetching groups for user {user_id}: {err}", level="warning")
                return group_list

            # Use extend with list comprehension for better performance
            group_list.extend(
                [
                    Group(
                        name=group.profile.name,
                        uid=group.id,
                        desc=group.profile.description,
                    )
                    for group in groups
                ]
            )

        return group_list

    async def get_user_mfa(self, user_id: str) -> bool:
        """Check if a user has MFA enabled.

        Args:
            user_id: The unique identifier of the user.

        Returns:
            True if the user has MFA factors configured, False otherwise.
        """
        factors, _, err = await self.client.list_factors(user_id)
        if err:
            self.log(f"Error while fetching MFA status for user {user_id}: {err}", level="warning")
            return False

        if not factors:
            self.log(f"No MFA factors found for user {user_id}", level="warning")
            return False

        return True

    async def get_user_roles(self, user_id: str) -> list[OktaRole]:
        """Get all roles for a specific user.

        Args:
            user_id: The unique identifier of the user.
        Returns:
            List of role names associated with the user.
        """
        roles, _, err = await self.client.list_assigned_roles_for_user(user_id)
        if err:
            self.log(f"Error while fetching roles for user {user_id}: {err}", level="warning")
            return []

        if not roles:
            self.log(f"No roles found for user {user_id}", level="debug")
            return []

        return list(roles)

    async def next_list_users(self) -> AsyncGenerator[OktaUser, None]:
        """Fetch all users from Okta.

        Returns:
            List of user objects from Okta.
        """
        try:
            query_params = {}
            if self.most_recent_date_seen:
                query_params = {"search": f'created gt "{self.most_recent_date_seen}"', "sortBy": "created", "sortOrder": "asc"}

            users, resp, err = await self.client.list_users(query_params)
            if err:
                self.log(f"Error while listing users: {err}", level="error")
                return
            
            for user in users:
                yield user
                self.new_most_recent_date = user.created

            while resp.has_next():
                users, resp, err = await resp.next()
                if err:
                    self.log(f"Error while listing users: {err}", level="error")
                    return
                for user in users:
                    yield user
                    self.new_most_recent_date = user.created

        except Exception as e:
            self.log(f"Exception while listing users: {e}", level="error")
            self.log_exception(e)
            return

    async def map_fields(self, okta_user: OktaUser) -> UserOCSFModel:
        """Map Okta user data to OCSF format.

        Args:
            okta_user: OktaUser object containing user data.

        Returns:
            UserOCSFModel instance with mapped user data.

        Raises:
            ValueError: If required user data is missing.
        """
        # Validate required fields
        if not okta_user.id:
            raise ValueError("User ID is required")
        if not okta_user.profile or not okta_user.profile.login:
            raise ValueError("User profile and login are required")

        # Handle None values in name fields
        first_name = okta_user.profile.firstName or "None"
        last_name = okta_user.profile.lastName or "None"
        full_name = f"{first_name} {last_name}".strip()

        account = Account(
            name=okta_user.profile.login,
            type_id=AccountTypeId.OTHER,
            type=AccountTypeStr.OTHER,
            uid=okta_user.id,
        )

        # Fetch user groups and MFA status concurrently
        groups_task = asyncio.create_task(self.get_user_groups(okta_user.id))
        mfa_task = asyncio.create_task(self.get_user_mfa(okta_user.id))
        roles_task = asyncio.create_task(self.get_user_roles(okta_user.id))

        groups = await groups_task
        has_mfa = await mfa_task
        roles = await roles_task

        # Extract domain from email address
        domain = None
        if okta_user.profile.email and "@" in okta_user.profile.email:
            domain = okta_user.profile.email.split("@")[1]

        # Get display name if available
        display_name = None
        if hasattr(okta_user.profile, "displayName"):
            display_name_value = okta_user.profile.displayName
            if display_name_value and isinstance(display_name_value, str):
                display_name = display_name_value

        # Determine user type based on userType field if available
        user_type_id = None
        user_type = None
        for role in roles:
            if role.status == OktaRoleStatus.ACTIVE and "admin" in role.type.lower():
                user_type_id = UserTypeId.ADMIN
                user_type = UserTypeStr.ADMIN
                break

        user = User(
            uid=okta_user.id,
            full_name=full_name,
            email_addr=okta_user.profile.email,
            name=okta_user.profile.login,
            account=account,
            groups=groups,
            has_mfa=has_mfa,
            display_name=display_name,
            domain=domain,
            uid_alt=okta_user.profile.login,
            type_id=user_type_id,
            type=user_type,
        )

        return UserOCSFModel(
            activity_id=2,
            activity_name="Collect",
            category_name="Discovery",
            category_uid=5,
            class_name="User Inventory Info",
            class_uid=5003,
            type_name="User Inventory Info: Collect",
            type_uid=5003002,
            severity="Informational",
            severity_id=1,
            time=isoparse(okta_user.created).timestamp(),
            metadata=Metadata(
                product=Product(
                    name="Okta",
                    vendor_name="Okta",
                    version="N/A",
                ),
                version="1.6.0",
            ),
            user=user,
        )

    async def get_assets(self) -> AsyncGenerator[UserOCSFModel, None]:
        """Generate user assets from Okta.

        Yields:
            UserOCSFModel instances for each user found in Okta.
        """
        self.log("Starting Okta user assets generator", level="info")
        self.log(f"Data path: {self._data_path.absolute()}", level="info")

        async for user in self.next_list_users():
            try:
                yield await self.map_fields(user)
            except Exception as e:
                user_id = getattr(user, "id", "unknown")
                self.log(f"Error while mapping user {user_id}: {e}", level="error")
                continue
