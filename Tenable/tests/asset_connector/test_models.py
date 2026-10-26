import pytest
from pydantic import ValidationError

from tenable_conn.asset_connector.models.asset_details_model import AssetDetails
from tenable_conn.asset_connector.models.assets_export_model import AssetExportV2
from tenable_conn.asset_connector.models.vuln_export_model import Vulnerability


def test_vulnerability_accepts_null_optional_fields(vulnerability):
    vuln = Vulnerability.model_validate(
        {**vulnerability, "plugin": {**vulnerability["plugin"], "see_also": None, "cve": None}, "state": None}
    )

    assert vuln.plugin.see_also == []
    assert vuln.plugin.cve == []
    assert vuln.state is None


def test_asset_export_accepts_null_optional_fields():
    asset = AssetExportV2.model_validate(
        {
            "id": "asset-1",
            "name": None,
            "operating_systems": None,
            "network": {"ipv4s": None, "hostnames": None, "network_interfaces": [{"ipv4s": None}]},
        }
    )

    assert asset.operating_systems == []
    assert asset.network.ipv4s == []
    assert asset.network.network_interfaces[0].ipv4s == []


def test_asset_export_null_on_required_field_still_fails():
    with pytest.raises(ValidationError):
        AssetExportV2.model_validate({"id": None})
    with pytest.raises(ValidationError):
        AssetExportV2.model_validate({"id": "asset-1", "tags": [{"uuid": None, "key": "env", "value": "prod"}]})


def test_asset_details_accepts_null_optional_fields():
    details = AssetDetails.model_validate({"id": "asset-1", "ipv4": None, "tags": [{"tag_uuid": None}]})

    assert details.tags[0].tag_uuid is None
