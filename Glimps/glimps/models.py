"""
Data models of the Glimps module
"""

from pydantic import BaseModel, Field, validator
from sekoia_automation.module import Module
from typing_extensions import TypedDict, NotRequired


class GlimpsConfiguration(BaseModel):
    api_key: str = Field(..., secret=True, description="Glimps detect token")
    base_url: str = Field(..., description="Glimps detect url")


class GlimpsModule(Module):
    configuration: GlimpsConfiguration


class SubmitArgument(BaseModel):
    file_name: str = Field(..., description="name of submitted file")
    bypass_cache: bool = Field(
        default=False,
        description="If True, the file is analyzed, even if a result already exists",
    )
    user_tags: tuple = Field(
        default=(), description="If filled, the file will be tagged with those tags"
    )
    description: str | None = Field(
        description=" If filled, a description will be added to the analysis"
    )
    archive_pwd: str | None = Field(
        description="If filled, the password used to extract archive"
    )
    push_timeout: float = Field(
        default=30,
        description="The maximum time (in seconds) to wait for a response when submitting file",
    )


class WaitForResultArgument(SubmitArgument):
    pull_time: float = Field(
        default=1.0,
        description="The time to wait (in seconds) between each requests to get a result",
    )
    timeout: float = Field(
        default=180, description="The maximum time execution of this method in seconds"
    )


class SearchAnalysisBySha256Argument(BaseModel):
    sha256: str = Field(..., description="sha256 of file to search")


class GetAnalysisByUUIDArgument(BaseModel):
    uuid: str = Field(..., description="uuid of analysis")


class SubmitResponse(BaseModel):
    status: bool = Field(default=False, description="False means that an error occured")
    uuid: str = Field(default=None, description="uuid of the submitted analysis")


class Tag(TypedDict):
    name: str
    value: str


class Threat(TypedDict):
    filenames: list[str]
    tags: list[Tag]
    score: int
    magic: str
    sha256: str
    sha1: str
    md5: str
    ssdeep: str
    file_size: int
    mime: str


class AvResult(TypedDict):
    av: str
    result: str
    score: int


class FileResult(TypedDict):
    sha256: str
    sha1: str
    md5: str
    magic: str
    size: int
    is_malware: bool
    av_result: NotRequired[list[AvResult]]


class AnalysisResponse(BaseModel):
    status: bool = Field(description="false means an error occured")
    special_status_code: int = Field(
        description="special error code, 0 means no special case"
    )
    uuid: str = Field(description="Unique analysis identifier")
    sha256: str = Field(description="string hex encoded input file SHA256")
    sha1: str = Field(description="string hex encoded input file SHA1")
    md5: str = Field(description="string hex encoded input file MD5")
    ssdeep: str = Field(description="string input file SSDeep")
    is_malware: bool = Field(description="analysis result, is a malware or not")
    score: int = Field(description="highest score given by probes")
    done: bool = Field(description="is analysis finished")
    timestamp: int = Field(
        description="timestamp of the start of analysis in milliseconds"
    )
    file_count: int = Field(
        description="amount of file in the submission (input + extracted)"
    )
    duration: int = Field(description="duration of the analysis in milliseconds")
    filetype: str = Field(description="type of the file")
    size: int = Field(description="input file size (in bytes)")

    # non required fields below
    sid: str = Field(
        default=None,
        description="analysis UUID handled by GLIMPS malware finder - expert\ncould be used to construct expert link like:\nhttps://gmalware.useddomain.glimps.re/expert/en/analysis/results/advanced/${SID}",
    )
    token: str = Field(
        default=None,
        description="token that can be used to view analysis result in expert view",
    )
    error: str = Field(default=None, description="error message if Status is false")
    errors: dict[str, str] = Field(
        default=None, description="error message by services"
    )
    filenames: list[str] = Field(default=None, description="list of analysed filename")
    malwares: list[str] = Field(
        default=None, description="list of malware names found in analysis"
    )
    files: list[FileResult] = Field(
        default=None,
        description="array of submission files (input file and extracted sub-files)",
    )
    threats: dict[str, Threat] = Field(
        default=None,
        description="Summary of threats found in submission. Each submission file reaching threshold score will add an entry. Entry keys are the SHA256 of files",
    )


class ProfileStatus(BaseModel):
    daily_quota: int = Field(
        description="Number of submissions authorized for the profile within 24h."
    )
    available_daily_quota: int = Field(
        description="Number of submissions still available within 24h. It's a sliding window, so a new slot will be released 24h after each submission."
    )
    cache: bool = Field(
        description="If True, the profile is configured to use cached result by default."
    )
    estimated_analysis_duration: int = Field(
        description="t's an estimation of the duration for the next submissions in milliseconds. It's based on the average time of submissions and the submission queue state. The real duration could differ from the estimation."
    )


class ExportSubmissionArguments(BaseModel):
    uuid: str = Field(description="Unique analysis identifier")
    format: str = Field(description="export format")
    layout: str = Field(description="export layout")
    is_full: str = Field(
        default=False, description="should export full analysis or summarized"
    )

    @validator("format")
    def check_format(cls, v: str):
        allowed_format = ["misp", "stix", "json", "pdf", "markdown", "csv"]
        if v not in allowed_format:
            raise ValueError(f"format must be on of {allowed_format}")
        return v

    @validator("layout")
    def check_layout(cls, v: str):
        allowed_layout = ["fr", "en"]
        if v not in allowed_layout:
            raise ValueError(f"format must be on of {allowed_layout}")
        return v
