import pytest
from pydantic import ValidationError

from thor_cloud_modules import client
from thor_cloud_modules.action_generate_launcher import GenerateLauncherAction, GenerateLauncherArguments
from thor_cloud_modules.models import ThorCloudModuleConfiguration


@pytest.fixture
def action(tmp_path):
    instance = GenerateLauncherAction(data_path=tmp_path)
    instance.module._configuration = ThorCloudModuleConfiguration(api_key="api-key")
    return instance


def test_generate_windows_launcher(action, monkeypatch):
    monkeypatch.setattr(
        client, "fetch_campaign", lambda *_args: {"id": "camp-1", "name": "Existing", "active": True}
    )
    monkeypatch.setattr(client, "fetch_launcher_token", lambda *_args: "campaign-token")

    result = action.run(
        GenerateLauncherArguments(
            campaign_id="camp-1",
            launcher_type="windows-powershell",
            product="thor_cloud",
        )
    )

    assert result["campaign_id"] == "camp-1"
    assert result["campaign_name"] == "Existing"
    assert result["campaign_created"] is False
    assert result["filename"] == "thor-cloud-launcher.ps1"
    assert result["launcher_url"].startswith("https://thorcloud.nextron-services.com/api/v1/")
    assert "type=windows-powershell" in result["launcher_url"]
    assert "token=campaign-token" in result["launcher_url"]
    assert "Invoke-WebRequest" in result["command"]
    assert "& $launcherPath" in result["command"]


@pytest.mark.parametrize("launcher_type", ["linux-bash", "mac-bash"])
def test_generate_shell_launcher(action, monkeypatch, launcher_type):
    monkeypatch.setattr(client, "fetch_campaign", lambda *_args: {"id": "camp-1", "active": True})
    monkeypatch.setattr(client, "fetch_launcher_token", lambda *_args: "campaign-token")

    result = action.run(GenerateLauncherArguments(campaign_id="camp-1", launcher_type=launcher_type))

    assert result["filename"] == "thor-cloud-launcher.sh"
    assert "curl --fail --location" in result["command"]
    assert 'chmod 700 "$launcher_path"' in result["command"]
    assert f"type={launcher_type}" in result["launcher_url"]


def test_inactive_campaign_does_not_issue_token(action, monkeypatch):
    monkeypatch.setattr(client, "fetch_campaign", lambda *_args: {"id": "camp-1", "active": False})
    token_requested = False

    def fetch_token(*_args):
        nonlocal token_requested
        token_requested = True
        return "unused"

    monkeypatch.setattr(client, "fetch_launcher_token", fetch_token)

    with pytest.raises(ValueError, match="is not active"):
        action.run(GenerateLauncherArguments(campaign_id="camp-1", launcher_type="linux-bash"))

    assert token_requested is False


def test_mismatched_campaign_does_not_issue_token(action, monkeypatch):
    monkeypatch.setattr(client, "fetch_campaign", lambda *_args: {"id": "other", "active": True})
    monkeypatch.setattr(client, "fetch_launcher_token", lambda *_args: pytest.fail("must not request token"))

    with pytest.raises(ValueError, match="different from the requested campaign"):
        action.run(GenerateLauncherArguments(campaign_id="camp-1", launcher_type="linux-bash"))


def test_create_campaign_then_generate_launcher(action, monkeypatch):
    created_payload = None

    def create_campaign(_base_url, _headers, payload):
        nonlocal created_payload
        created_payload = payload
        return {"id": "new-camp", "name": "Incident scan", "active": True}

    monkeypatch.setattr(client, "create_campaign", create_campaign)
    monkeypatch.setattr(
        client,
        "fetch_scan_profiles",
        lambda *_args: [{"index": 1, "name": "Quick Scan"}, {"index": 2, "name": "Full Scan"}],
    )
    monkeypatch.setattr(
        client, "fetch_campaign", lambda *_args: {"id": "new-camp", "name": "Incident scan", "active": True}
    )
    monkeypatch.setattr(client, "fetch_launcher_token", lambda *_args: "campaign-token")

    result = action.run(
        GenerateLauncherArguments(
            campaign_mode="new",
            campaign_name="Incident scan",
            campaign_description="Created by a playbook",
            assigned_contract="contract-1",
            end_date="2026-12-31T23:00:00+01:00",
            scan_limit=10,
            scan_profile="Full Scan",
            scan_threads=4,
            launcher_type="linux-bash",
        )
    )

    assert created_payload == {
        "name": "Incident scan",
        "description": "Created by a playbook",
        "assigned_contract": "contract-1",
        "end_date": 1798754400,
        "scan_limit": 10,
        "scan_profile": 2,
        "scan_threads": 4,
    }
    assert result["campaign_id"] == "new-camp"
    assert result["campaign_name"] == "Incident scan"
    assert result["campaign_created"] is True
    assert "token=campaign-token" in result["launcher_url"]


def test_existing_mode_requires_campaign_id():
    with pytest.raises(ValueError, match="campaign_id is required"):
        GenerateLauncherArguments(launcher_type="linux-bash")


def test_new_mode_requires_campaign_name():
    with pytest.raises(ValueError, match="campaign_name is required"):
        GenerateLauncherArguments(campaign_mode="new", launcher_type="linux-bash")


def test_end_date_requires_timezone():
    with pytest.raises(ValidationError, match="end_date must include a timezone"):
        GenerateLauncherArguments(
            campaign_mode="new",
            campaign_name="Incident scan",
            end_date="2026-12-31T23:00:00",
            launcher_type="linux-bash",
        )


def test_unknown_scan_profile_is_rejected(action, monkeypatch):
    monkeypatch.setattr(client, "fetch_scan_profiles", lambda *_args: [{"index": 1, "name": "Quick Scan"}])

    with pytest.raises(ValueError, match="Available profiles: Quick Scan"):
        action.run(
            GenerateLauncherArguments(
                campaign_mode="new",
                campaign_name="Incident scan",
                scan_profile="Does not exist",
                launcher_type="linux-bash",
            )
        )
