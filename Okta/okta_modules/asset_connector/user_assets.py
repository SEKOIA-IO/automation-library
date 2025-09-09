import asyncio
from functools import cached_property
from collections.abc import AsyncGenerator, Generator
from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import (
    Metadata,
    Product,
)
from sekoia_automation.asset_connector.models.ocsf.user import (
    UserOCSFModel,
    User,
    Group,
    Account,
    AccountTypeId,
    AccountTypeStr
)
from sekoia_automation.storage import PersistentJSON

from okta.client import Client as OktaClient

class OktaUserAssetConnector(AssetConnector):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def most_recent_date_seen(self) -> str | None:
        with self.context as cache:
            most_recent_date_seen = cache.get("most_recent_date_seen", None)

            return most_recent_date_seen
        
    @cached_property
    def client(self):
        config = {
            'orgUrl': self.module.configuration["base_url"],
            'token': self.module.configuration["apikey"]
        }
        return OktaClient(config)

    async def map_fields(self, okta_user: dict) -> UserOCSFModel:
        account = Account(
            name=okta_user.get("profile", {}).get("login", ""),
            type_id=AccountTypeId.OTHER,
            type_str=AccountTypeStr.OTHER,
            uid=okta_user.get("id"),

        )
        user = User(
            uid=okta_user.get("id"),
            full_name=okta_user.get("profile", {}).get("firstName", "") + " " + okta_user.get("profile", {}).get("lastName", ""),
            email_addr=okta_user.get("profile", {}).get("email", ""),
            name=okta_user.get("profile", {}).get("login", ""),
            account=account,
            groups= await self.get_user_groups(okta_user.get("id"))
        )
        return UserOCSFModel(
            metadata=Metadata(
                product=Product(
                    name="Okta",
                    vendor="Okta",
                    version="N/A"
                ),
                version="1.6.0"
            ),
            user=user
        )

    async def get_user_groups(self, user_id: str) -> list[Group]:
        self.log(f"Fetching groups for user ID: {user_id}", level="info")
        groups, _, err = await self.client.list_user_groups(user_id)
        if err:
            self.log(f"Error while fetching groups for user {user_id}: {err}", level="error")
            return []
        if not groups:
            self.log(f"No groups found for user {user_id}", level="warning")
            return []
        group_list = []
        for group in groups:
            group_list.append(Group(
                name=group.get("profile", {}).get("name", ""),
                uid=group.get("id"),
                desc=group.get("profile", {}).get("description", "")
            ))
        return group_list
    
    async def get_user_mfa(self, user_id: str) -> bool:
        self.log(f"Fetching MFA status for user ID: {user_id}", level="info")
        factors, _, err = await self.client.user(user_id)
        if err:
            self.log(f"Error while fetching MFA status for user {user_id}: {err}", level="error")
            return False
        if not factors:
            self.log(f"No MFA factors found for user {user_id}", level="warning")
            return False
        return True

    async def next_list_users(self) -> list[dict]:
        self.log("Start the listing users generator !!", level="info")
        users, _, err = await self.client.list_users()
        if err:
            self.log(f"Error while listing users: {err}", level="error")
            return []
        if not users:
            self.log("No users found", level="warning")
            return []
        return users

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        self.log("Start the getting assets generator !!", level="info")
        self.log(f"The data path is: {self._data_path.absolute()}", level="info")
        for users in asyncio.run(self.next_list_users()):
            for user in users:
                mapped_user: UserOCSFModel = self.map_fields(user)
                yield mapped_user