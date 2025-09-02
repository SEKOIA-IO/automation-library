import boto3
from collections.abc import Generator

import pytz
from datetime import datetime
from dateutil.parser import isoparse

from sekoia_automation.storage import PersistentJSON

from sekoia_automation.asset_connector import AssetConnector
from typing import Optional
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
    AccountTypeStr,
)


class AwsUser:
    def __init__(self, user: User, date: datetime):
        self.user = user
        self.date = date


class AwsUsersAssetConnector(AssetConnector):
    PRODUCT_NAME: str = "AWS IAM"

    def __init__(self, *args: object, **kwargs: object):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def most_recent_date_seen(self) -> Optional[str]:
        with self.context as cache:
            value = cache.get("most_recent_date_seen")
            return value if value is None or isinstance(value, str) else str(value)

    def client(self) -> boto3.client:
        session = boto3.Session(
            aws_access_key_id=self.module.configuration["aws_access_key"],
            aws_secret_access_key=self.module.configuration["aws_secret_access_key"],
            region_name=self.module.configuration["aws_region_name"],
        )
        return session.client("iam")

    def get_groups_for_user(self, user_name: str) -> list[Group]:
        self.log(f"Start fetching groups for user {user_name}...", level="info")
        paginator = self.client().get_paginator("list_groups_for_user")
        page_iterator = paginator.paginate(UserName=user_name)
        groups = []
        for page in page_iterator:
            for group in page["Groups"]:
                group_obj = Group(
                    name=group["GroupName"],
                    uid=group["Arn"],
                )
                self.log(f"Fetched group: {group_obj.name} for user: {user_name}", level="debug")
                groups.append(group_obj)
        return groups

    def get_mfa_status_for_user(self, user_name: str) -> bool:
        self.log(f"Start fetching MFA status for user {user_name}...", level="info")
        response = self.client().list_mfa_devices(UserName=user_name)
        has_mfa = len(response["MFADevices"]) > 0
        self.log(f"User {user_name} has MFA: {has_mfa}", level="debug")
        return has_mfa

    def get_aws_users(self) -> Generator[list[AwsUser], None, None]:
        self.log("Start fetching AWS users...", level="info")
        paginator = self.client().get_paginator("list_users")
        page_iterator = paginator.paginate()
        date_filter: datetime | None = isoparse(self.most_recent_date_seen) if self.most_recent_date_seen else None
        for page in page_iterator:
            users = []
            for user in page["Users"]:
                created_time: datetime = user["CreateDate"]
                created_time = created_time.replace(tzinfo=pytz.UTC)
                if date_filter and (created_time < date_filter):
                    continue
                account = Account(
                    name=user["UserName"],
                    type=AccountTypeStr.AWS_ACCOUNT,
                    type_id=AccountTypeId.AWS_ACCOUNT,
                    uid=user["Arn"],
                )
                user_obj = User(
                    name=user["UserName"],
                    uid=user["Arn"],
                    groups=self.get_groups_for_user(user["UserName"]),
                    has_mfa=self.get_mfa_status_for_user(user["UserName"]),
                    account=account,
                )
                self.log(f"Fetched user: {user_obj.name}", level="debug")
                users.append(AwsUser(user=user_obj, date=user["CreateDate"]))
            yield users

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        self.log("Start the getting assets generator...", level="info")
        self.log(f"The data path is: {self._data_path.absolute()}", level="info")
        new_most_recent_date = datetime.now().replace(tzinfo=pytz.UTC).isoformat()
        for aws_users in self.get_aws_users():
            for aws_user in aws_users:
                product = Product(name=self.PRODUCT_NAME, version="1.0.0")
                metadata = Metadata(product=product, version="1.6.0")
                user_ocsf = UserOCSFModel(
                    activity_id=2,
                    activity_name="Collect",
                    category_name="Discovery",
                    category_uid=5,
                    class_name="User Inventory",
                    class_uid=5003,
                    type_name="User Inventory Info: Collect",
                    type_uid=500301,
                    time=aws_user.date.timestamp(),
                    metadata=metadata,
                    user=aws_user.user,
                )
                yield user_ocsf
        with self.context as cache:
            cache["most_recent_date_seen"] = new_most_recent_date
