"""Generate a campaign-scoped THOR Cloud launcher URL and bootstrap command."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator
from sekoia_automation.action import Action

from thor_cloud_modules import client


LauncherType = Literal["windows-powershell", "linux-bash", "mac-bash"]
Product = Literal["thor_cloud", "thor_cloud_lite"]


class GenerateLauncherArguments(BaseModel):
    campaign_mode: Literal["existing", "new"] = "existing"
    campaign_id: str | None = None
    campaign_name: str | None = None
    campaign_description: str | None = None
    assigned_contract: str | None = None
    end_date: datetime | None = None
    scan_limit: int | None = Field(default=None, ge=0)
    scan_profile: str | None = None
    scan_threads: int | None = Field(default=None, ge=1)
    launcher_type: LauncherType
    product: Product = "thor_cloud_lite"

    @model_validator(mode="after")
    def validate_campaign_selection(self):
        if self.campaign_mode == "existing" and not self.campaign_id:
            raise ValueError("campaign_id is required when campaign_mode is existing")
        if self.campaign_mode == "new" and not self.campaign_name:
            raise ValueError("campaign_name is required when campaign_mode is new")
        if self.end_date is not None and self.end_date.utcoffset() is None:
            raise ValueError("end_date must include a timezone")
        return self


class GenerateLauncherAction(Action):
    """Generate launcher material without coupling THOR Cloud to an EDR."""

    name = "Generate THOR Cloud launcher"
    description = (
        "Link or create a THOR Cloud campaign, then generate a tokenized launcher URL and bootstrap command"
    )

    @staticmethod
    def _command(launcher_type: LauncherType, launcher_url: str) -> tuple[str, str]:
        if launcher_type == "windows-powershell":
            filename = "thor-cloud-launcher.ps1"
            command = (
                "$launcherPath = Join-Path $env:TEMP 'thor-cloud-launcher.ps1'; "
                f"Invoke-WebRequest -UseBasicParsing -Uri '{launcher_url}' -OutFile $launcherPath; "
                "& $launcherPath"
            )
            return filename, command

        filename = "thor-cloud-launcher.sh"
        command = (
            "launcher_path=$(mktemp /tmp/thor-cloud-launcher.XXXXXX); "
            f"curl --fail --location --silent --show-error '{launcher_url}' --output \"$launcher_path\"; "
            "chmod 700 \"$launcher_path\"; \"$launcher_path\""
        )
        return filename, command

    def run(self, arguments: GenerateLauncherArguments) -> dict:
        base_url = client.get_base_url(arguments.product)
        headers = client.get_headers(self.module.configuration.api_key)

        if arguments.campaign_mode == "new":
            scan_profile_index = None
            if arguments.scan_profile:
                profiles = client.fetch_scan_profiles(base_url, headers)
                matching_profiles = [
                    profile
                    for profile in profiles
                    if str(profile.get("name", "")).casefold() == arguments.scan_profile.strip().casefold()
                ]
                if len(matching_profiles) != 1 or not isinstance(matching_profiles[0].get("index"), int):
                    available = ", ".join(
                        sorted(str(profile["name"]) for profile in profiles if profile.get("name"))
                    )
                    raise ValueError(
                        f"Unknown or ambiguous THOR Cloud scan profile {arguments.scan_profile!r}. "
                        f"Available profiles: {available or 'none'}"
                    )
                scan_profile_index = matching_profiles[0]["index"]

            campaign = client.create_campaign(
                base_url,
                headers,
                {
                    "name": arguments.campaign_name,
                    "description": arguments.campaign_description,
                    "assigned_contract": arguments.assigned_contract,
                    "end_date": int(arguments.end_date.timestamp()) if arguments.end_date else None,
                    "scan_limit": arguments.scan_limit,
                    "scan_profile": scan_profile_index,
                    "scan_threads": arguments.scan_threads,
                },
            )
            campaign_id = campaign["id"]
        else:
            campaign_id = arguments.campaign_id

        campaign = client.fetch_campaign(base_url, headers, campaign_id)
        if campaign.get("id") != campaign_id:
            raise ValueError("THOR Cloud returned a campaign different from the requested campaign")
        if not campaign.get("active", False):
            raise ValueError(f"THOR Cloud campaign {campaign_id} is not active")

        token = client.fetch_launcher_token(base_url, headers, campaign_id)
        launcher_url = client.build_launcher_url(base_url, token, arguments.launcher_type)
        filename, command = self._command(arguments.launcher_type, launcher_url)

        return {
            "campaign_id": campaign_id,
            "campaign_name": campaign.get("name") or arguments.campaign_name,
            "campaign_created": arguments.campaign_mode == "new",
            "launcher_type": arguments.launcher_type,
            "launcher_url": launcher_url,
            "filename": filename,
            "command": command,
        }
