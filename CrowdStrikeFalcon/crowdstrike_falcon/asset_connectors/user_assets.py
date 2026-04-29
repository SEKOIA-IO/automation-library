from functools import cached_property
from collections.abc import Generator
from datetime import datetime

from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.user import (
    UserOCSFModel,
    User as UserOCSF,
    Account,
    AccountTypeId,
    AccountTypeStr,
    UserEnrichmentObject,
    UserDataObject,
    UserTypeId,
    UserTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.risk_level import RiskLevelId, RiskLevelStr
from sekoia_automation.storage import PersistentJSON

from crowdstrike_falcon.asset_connectors.crowdstrike_user_model import CrowdStrikeUser, CrowdStrikeUserAccount
from crowdstrike_falcon.client import CrowdstrikeFalconClient

IDENTITY_ENTITIES_QUERY = """
{
  entities(
    types: [USER]
    sortKey: PRIMARY_DISPLAY_NAME
    sortOrder: ASCENDING
    first: 50
    {cursor}
  ) {
    pageInfo {
      hasNextPage
      endCursor
    }
    nodes {
      entityId
      type
      primaryDisplayName
      secondaryDisplayName
      creationTime
      riskScore
      riskScoreSeverity
      accounts {
        dataSource
        ... on ActiveDirectoryAccountDescriptor {
          domain
          samAccountName
          objectSid
          objectGuid
          enabled
        }
      }
      ... on UserEntity {
        emailAddresses
      }
      roles {
        type
      }
    }
  }
}
"""


class CrowdstrikeUserAssetConnector(AssetConnector):
    PRODUCT_NAME: str = "Crowdstrike Falcon"
    PRODUCT_VERSION = "N/A"
    LIMIT: int = 100
    CHECKPOINT_KEY = "user_assets_last_seen_timestamp"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def most_recent_user_date(self) -> str | None:
        with self.context as cache:
            return cache.get(self.CHECKPOINT_KEY, None)

    def update_checkpoint(self) -> None:
        """
        Update the checkpoint with the most recent date.

        This method updates the persistent storage with the latest processed date
        to enable incremental data collection.
        """
        if self._latest_time is None:
            self.log("Warning: new_most_recent_date is None, skipping checkpoint update", level="warning")
            return

        try:
            with self.context as cache:
                cache[self.CHECKPOINT_KEY] = self._latest_time
                self.log(f"Checkpoint updated with date: {self._latest_time}", level="info")
        except Exception as e:
            self.log(f"Failed to update checkpoint: {str(e)}", level="error")
            self.log_exception(e)

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

    def _parse_timestamp(self, timestamp: str | None) -> int:
        """
        Parse ISO 8601 timestamp to Unix epoch.

        Args:
            timestamp: ISO 8601 formatted timestamp string.

        Returns:
            Unix timestamp as integer, or 0 if parsing fails.
        """
        if not timestamp:
            return 0
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except (ValueError, AttributeError):
            return 0

    def _map_risk_level(self, severity: str | None) -> tuple[RiskLevelId | None, RiskLevelStr | None]:
        """
        Map Crowdstrike risk severity to OCSF risk level.

        Args:
            severity (str | None): The severity string from Crowdstrike.
        Returns:
            tuple[RiskLevelId | None, RiskLevelStr | None]: Corresponding OCSF risk level ID and string.
        """
        if not severity:
            return None, None
        mapping = {
            "CRITICAL": (RiskLevelId.CRITICAL, RiskLevelStr.CRITICAL),
            "HIGH": (RiskLevelId.HIGH, RiskLevelStr.HIGH),
            "MEDIUM": (RiskLevelId.MEDIUM, RiskLevelStr.MEDIUM),
            "LOW": (RiskLevelId.LOW, RiskLevelStr.LOW),
            "INFO": (RiskLevelId.INFO, RiskLevelStr.INFO),
        }
        return mapping.get(severity.upper(), (None, None))

    def _determine_account_type(self, account: CrowdStrikeUserAccount) -> tuple[AccountTypeId, AccountTypeStr]:
        """
        Account type determination based on data source and attributes.
        Args:
            account (CrowdStrikeUserAccount): The account data from Crowdstrike.
        Returns:
            tuple[AccountTypeId, AccountTypeStr]: Corresponding OCSF account type ID and string.
        """
        data_source = (account.dataSource or "").upper()
        if "ACTIVE_DIRECTORY" in data_source or account.objectSid is not None:
            return AccountTypeId.LDAP_ACCOUNT, AccountTypeStr.LDAP_ACCOUNT
        if "AZURE" in data_source:
            return AccountTypeId.AZURE_AD_ACCOUNT, AccountTypeStr.AZURE_AD_ACCOUNT
        return AccountTypeId.OTHER, AccountTypeStr.OTHER

    def _determine_user_type(self, entity: CrowdStrikeUser) -> tuple[UserTypeId, UserTypeStr]:
        """
        Determine user type based on roles.
        Args:
            entity (CrowdStrikeUser): The user entity data from Crowdstrike.
        Returns:
            tuple[UserTypeId, UserTypeStr]: Corresponding OCSF user type ID and string.
        """
        for role in entity.roles:
            if "ADMIN" in (role.type or "").upper():
                return UserTypeId.ADMIN, UserTypeStr.ADMIN
        return UserTypeId.USER, UserTypeStr.USER

    def map_identity_entity_fields(self, entity: CrowdStrikeUser) -> UserOCSFModel:
        """Map fields from Crowdstrike identity entity to OCSF User model."""

        metadata = Metadata(product=Product(name=self.PRODUCT_NAME, version=self.PRODUCT_VERSION), version="1.6.0")

        entity_id = entity.entityId or "Unknown"
        primary_name = entity.primaryDisplayName or ""
        email_addresses = entity.emailAddresses

        account_data, domain, enrichments = None, None, []

        if entity.accounts:
            acc = entity.accounts[0]
            account_type_id, account_type_str = self._determine_account_type(acc)
            domain = acc.domain

            account_data = Account(
                name=acc.samAccountName or primary_name,
                type_id=account_type_id,
                type=account_type_str,
                uid=acc.objectSid or acc.objectGuid or entity_id,
            )

            enrichments.append(
                UserEnrichmentObject(
                    name="account_details",
                    value=account_type_str.value,
                    data=UserDataObject(is_enabled=acc.enabled),
                )
            )

        risk_level_id, risk_level_str = self._map_risk_level(entity.riskScoreSeverity)
        user_type_id, user_type_str = self._determine_user_type(entity)

        user_ocsf = UserOCSF(
            name=primary_name,
            uid=entity_id,
            account=account_data,
            full_name=f"{primary_name} {entity.secondaryDisplayName or ''}".strip() or None,
            email_addr=email_addresses[0] if email_addresses else None,
            domain=domain,
            risk_level=risk_level_str,
            risk_level_id=risk_level_id,
            risk_score=int((entity.riskScore or 0) * 100),
            type_id=user_type_id,
            type=user_type_str,
        )

        time_value = self._parse_timestamp(entity.creationTime)

        return UserOCSFModel(
            activity_id=2,
            activity_name="Collect",
            category_name="Discovery",
            category_uid=5,
            class_name="User Inventory Info",
            class_uid=5003,
            type_uid=500302,
            type_name="User Inventory",
            severity="Informational",
            severity_id=1,
            time=time_value,
            metadata=metadata,
            user=user_ocsf,
            enrichments=enrichments or None,
        )

    def _fetch_identity_entities(self) -> Generator[CrowdStrikeUser, None, None]:
        """
        Fetch identity entities from Crowdstrike with checkpointing.
        """
        checkpoint = self.most_recent_user_date
        most_recent_date: str | None = checkpoint

        if checkpoint:
            self.log(f"Resuming from checkpoint: {checkpoint}", level="info")

        for raw_entity in self.client.list_identity_entities(IDENTITY_ENTITIES_QUERY):
            entity = CrowdStrikeUser.model_validate(raw_entity)
            asset_date = entity.creationTime

            if checkpoint and asset_date and asset_date <= checkpoint:
                continue

            if asset_date and (not most_recent_date or asset_date > most_recent_date):
                most_recent_date = asset_date

            yield entity
        if most_recent_date and most_recent_date != checkpoint:
            self._latest_time = most_recent_date
            self.update_checkpoint()
            self.log(f"Checkpoint updated to: {most_recent_date}", level="info")

    def get_assets(self) -> Generator[UserOCSFModel, None, None]:
        """Retrieve user assets from Crowdstrike and map them to OCSF models."""
        self.log("Fetching users from Identity Protection GraphQL endpoint", level="info")
        for entity in self._fetch_identity_entities():
            yield self.map_identity_entity_fields(entity)
