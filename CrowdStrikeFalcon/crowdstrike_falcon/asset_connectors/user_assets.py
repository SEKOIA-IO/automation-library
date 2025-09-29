from functools import cached_property
from collections.abc import Generator
from typing import Any
from datetime import datetime

from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import (
    Metadata,
    Product,
)
from sekoia_automation.asset_connector.models.ocsf.user import (
    UserOCSFModel,
    User as UserOCSF,
    Account,
    AccountTypeId,
    AccountTypeStr,
    UserEnrichmentObject,
    UserDataObject,
)
from sekoia_automation.storage import PersistentJSON

from crowdstrike_falcon.client import CrowdstrikeFalconClient


class CrowdstrikeUserAssetConnector(AssetConnector):

    PRODUCT_NAME: str = "Crowdstrike Falcon"
    PRODUCT_VERSION = "1.0"
    LIMIT: int = 100

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)
        self._latest_id = None

    @property
    def most_recent_user_id(self) -> str | None:
        with self.context as cache:
            most_recent_id = cache.get("most_recent_user_id", None)

            return most_recent_id

    @cached_property
    def _http_default_headers(self) -> dict[str, str]:
        return {
            "User-Agent": "sekoiaio-connector/{0}-{1}".format(
                self.module.manifest.get("slug"), self.module.manifest.get("version")
            ),
        }

    @cached_property
    def client(self):
        return CrowdstrikeFalconClient(
            self.module.configuration.base_url,
            self.module.configuration.client_id,
            self.module.configuration.client_secret,
            default_headers=self._http_default_headers,
        )

    def map_user_fields(self, user: dict[str, Any]) -> UserOCSFModel:
        product = Product(
            name=self.PRODUCT_NAME,
            version=self.PRODUCT_VERSION,
        )
        metadata = Metadata(product=product, version="1.6.0")
        user_full_name = user.get("first_name", "") + " " + user.get("last_name", "")
        user_name = user.get("first_name", "").lower() + "." + user.get("last_name", "").lower()
        user_uuid = user.get("uuid", "Unknown")
        user_object = UserEnrichmentObject(
            name="login ",
            value="infos",
            data=UserDataObject(
                is_enabled=True if user.get("status") == "active" else False, last_logon=user.get("last_login_at")
            ),
        )
        enrichments_data = [user_object]
        account = Account(
            name=user_name,
            type_id=AccountTypeId.OTHER,
            type=AccountTypeStr.OTHER,
            uid=user_uuid,
        )
        user_data = UserOCSF(
            has_mfa=True if user.get("factors") else False,
            name=user_name,
            uid=user_uuid,
            full_name=user_full_name,
            email_addr=user.get("uid", "Unknown"),
            account=account,
        )
        user_ocsf_model = UserOCSFModel(
            activity_id=2,
            activity_name="Collect",
            category_name="Discovery",
            category_uid=5,
            class_name="User Inventory Info",
            class_uid=5003,
            type_uid=500302,
            severity="Informational",
            severity_id=1,
            time=datetime.timestamp(user.get("created_at")) if user.get("created_at") is not None else 0,
            metadata=metadata,
            user=user_data,
            enrichments=enrichments_data,
            type_name="User Inventory",
        )
        return user_ocsf_model

    def update_checkpoint(self) -> None:
        if self._latest_id is None:
            return
        with self.context as cache:
            cache["most_recent_user_id"] = self._latest_id

    def next_users(self) -> Generator[dict[str, Any], None, None]:
        last_first_uuid = self.most_recent_user_id
        uuids_batch: list[str] = []

        for idx, user_uuid in enumerate(self.client.list_users_uuids(limit=self.LIMIT, sort="created_at.desc")):
            if idx == 0:
                if user_uuid == last_first_uuid:
                    self.log("No user has been added !!", level="info")
                    return
                self._latest_id = user_uuid

            # Stopping before the last seen user id
            if last_first_uuid and user_uuid == last_first_uuid:
                break

            uuids_batch.append(user_uuid)

            if len(uuids_batch) >= self.LIMIT:
                for user_info in self.client.get_users_infos(uuids_batch):
                    yield user_info
                uuids_batch = []

        if uuids_batch:
            for user_info in self.client.get_users_infos(uuids_batch):
                yield user_info

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        self.log("Start the getting assets generator !!", level="info")
        for user in self.next_users():
            yield self.map_user_fields(user)
