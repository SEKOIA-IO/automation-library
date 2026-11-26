from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator


class UrlScanModuleConfiguration(BaseModel):
    api_key: str = Field(
        title="API key",
        description=(
            "urlscan.io API key. A team API key is recommended: "
            "scans submitted with it are visible to every team member"
        ),
        json_schema_extra={"secret": True},
    )
    base_url: str = Field(default="https://urlscan.io", title="Base URL", description="Base URL of the urlscan.io API")


class ActionArguments(BaseModel):
    """Arguments of an action, mirroring the `arguments` schema of its JSON descriptor (the source of truth).

    Strings are trimmed; null or empty values mean "not set" and fall back to the defaults of the descriptor.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def _drop_unset(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {key: value for key, value in data.items() if value is not None and value != "" and value != []}
        return data


Tag = Annotated[str, StringConstraints(max_length=30)]


class ScanUrlArguments(ActionArguments):
    url: str = Field(min_length=1, description="The URL to scan")
    customagent: str | None = Field(default=None, description="Override the HTTP User-Agent used by urlscan.io")
    visibility: Literal["public", "unlisted", "private"] = Field(
        default="private",
        description="Visibility of the scan: public, unlisted or private. A public scan is visible to everyone",
    )
    tags: list[Tag] = Field(
        default_factory=list,
        max_length=10,
        description="User tags, for example phishing (at most 10, 30 characters each)",
    )
    country: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z]{2}$",
        description=(
            "Two-letter ISO 3166-1 alpha-2 code of the country to scan from, for example fr. "
            "urlscan.io detects it when empty"
        ),
    )
    fail_on_blacklisted_url: bool = Field(
        default=True,
        description="When false, a URL blacklisted by urlscan.io returns the status blacklisted instead of failing",
    )
    wait_for_result: bool = Field(
        default=True,
        description=(
            "When false, return right after the submission with the status submitted; use Get scan result later"
        ),
    )
    timeout: int = Field(default=120, ge=30, le=600, description="Maximum time to wait for the scan, in seconds")


class ScanIdArguments(ActionArguments):
    """Arguments of Get scan result and Download scan screenshot."""

    scan_id: str = Field(description="UUID of a finished scan (urlscan.io scanId)")


class SearchArguments(ActionArguments):
    indicator: str | None = Field(
        default=None, description="IP address, domain, URL or SHA256 to search for; provide this or query"
    )
    query: str | None = Field(
        default=None,
        description=(
            "Elasticsearch Query String query, sent as the q parameter, for example "
            'task.tags:"phishing" AND date:>now-7d; values with colons, slashes or spaces must be double-quoted; '
            "provide this or indicator"
        ),
    )
    size: int = Field(default=100, ge=1, le=10000, description="Number of results in the page")
    search_after: str | None = Field(
        default=None,
        description="next_search_after of the previous call (comma-separated sort values of its last result), "
        "to get the next page",
    )
