import pytest
from datetime import datetime
from unittest.mock import Mock

from crowdstrike_falcon.asset_connectors.user_assets import CrowdstrikeUserAssetConnector


class _DummyContext(dict):
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        pass


@pytest.fixture
def connector():
    class FakeCrowdStrikeUserModule:
        configuration = {
            "sekoia_base_url": "https://api.fake.sekoia.io/",
            "frequency": 60,
            "sekoia_api_key": "fake_api_key",
        }
        manifest = {
            "client_id": "fake_client_id",
            "client_secret": "fake_client_secret",
            "base_url": "https://api.fake"
        }

    c = CrowdstrikeUserAssetConnector(module=FakeCrowdStrikeUserModule())
    c.context = _DummyContext()
    c.log = Mock()
    return c


def test_map_user_fields_happy_path(connector):
    now = datetime.now()
    user = {
        "first_name": "Alice",
        "last_name": "Smith",
        "uuid": "uuid-123",
        "uid": "alice@example.com",
        "status": "active",
        "factors": ["totp"],
        "created_at": now,
        "last_login_at": now.isoformat(),
    }
    result = connector.map_user_fields(user)
    assert result.user.full_name == "Alice Smith"
    assert result.user.uid == "uuid-123"
    assert result.user.email_addr == "alice@example.com"
    assert result.user.has_mfa is True
    assert result.time == pytest.approx(now.timestamp(), rel=1e-3)
    assert result.enrichments[0].data.is_enabled is True


def test_map_user_fields_missing_optional_fields(connector):
    user = {}
    result = connector.map_user_fields(user)
    assert result.user.full_name == " "
    assert result.user.uid == "Unknown"
    assert result.user.email_addr == "Unknown"
    assert result.user.has_mfa is False
    assert result.time == 0
    assert result.enrichments[0].data.is_enabled is False


def test_next_users_no_new_users_logs_and_stops(connector):
    connector.context["most_recent_user_id"] = "u1"
    connector.client = Mock()
    connector.client.list_users_uuids.return_value = ["u1", "u0"]
    produced = list(connector.next_users())
    assert produced == []
    connector.log.assert_called()
    assert connector._latest_id is None


def test_next_users_stops_before_last_seen(connector):
    connector.context["most_recent_user_id"] = "u2"
    connector.client = Mock()
    connector.client.list_users_uuids.return_value = ["u3", "u2", "u1"]
    connector.client.get_users_infos.side_effect = lambda batch: [{"uuid": u} for u in batch]
    produced = list(connector.next_users())
    assert produced == [{"uuid": "u3"}]
    assert connector._latest_id == "u3"


def test_next_users_batches_and_updates_checkpoint(connector):
    connector.LIMIT = 2
    connector.client = Mock()
    connector.client.list_users_uuids.return_value = ["u5", "u4", "u3", "u2", "u1"]
    connector.client.get_users_infos.side_effect = lambda batch: [{"uuid": u} for u in batch]
    users = list(connector.next_users())
    assert [u["uuid"] for u in users] == ["u5", "u4", "u3", "u2", "u1"]
    assert connector._latest_id == "u5"
    connector.update_checkpoint()
    assert connector.context["most_recent_user_id"] == "u5"


def test_get_assets_yields_mapped_models(connector):
    sample_users = [
        {"first_name": "A", "last_name": "B", "uuid": "1"},
        {"first_name": "C", "last_name": "D", "uuid": "2"},
    ]
    connector.next_users = Mock(return_value=iter(sample_users))
    connector.map_user_fields = Mock(side_effect=lambda u: {"mapped": u["uuid"]})
    assets = list(connector.get_assets())
    assert assets == [{"mapped": "1"}, {"mapped": "2"}]
    assert connector.map_user_fields.call_count == 2
    connector.log.assert_called()


def test_update_checkpoint_does_nothing_without_latest_id(connector):
    connector.context["most_recent_user_id"] = "old"
    connector._latest_id = None
    connector.update_checkpoint()
    assert connector.context["most_recent_user_id"] == "old"
