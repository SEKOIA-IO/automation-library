"""
Data models of the Glimps module
"""

from pydantic import BaseModel, Field, validator
from sekoia_automation.module import Module
from typing_extensions import TypedDict, NotRequired
from gdetect.consts import EXPORT_FORMATS, EXPORT_LAYOUTS


class GLIMPSConfiguration(BaseModel):
    api_key: str = Field(..., secret=True, description="Glimps detect token")
    base_url: str = Field(..., description="Glimps detect url")


class GLIMPSModule(Module):
    configuration: GLIMPSConfiguration


class SubmitArgument(BaseModel):
    file_name: str = Field(..., description="Name of submitted file")
    bypass_cache: bool = Field(
        default=False,
        description="If true, file is analyzed, even if a result already exists",
    )
    user_tags: tuple = Field(default=(), description="Analysis will be tagged with those tags")
    description: str = Field(
        default=None,
        description="Description added to the analysis",
    )
    archive_pwd: str = Field(default=None, description="Password used to extract archive")
    push_timeout: float = Field(
        default=30,
        description="Maximum time (in seconds) to wait for a response when submitting file",
    )


class WaitForResultArgument(SubmitArgument):
    pull_time: float = Field(
        default=1.0,
        description="Time to wait (in seconds) between each requests to get a result",
    )
    timeout: float = Field(
        default=180,
        description="Maximum time (in seconds) to wait for the analysis to end",
    )


class SearchAnalysisBySha256Argument(BaseModel):
    sha256: str = Field(..., description="SHA256 of file to search")


class GetAnalysisByUUIDArgument(BaseModel):
    uuid: str = Field(..., description="UUID of the analysis")


class SubmitResponse(BaseModel):
    status: bool = Field(default=False, description="False means that an error occured")
    uuid: str = Field(default=None, description="UUID of the submitted analysis")


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


class AnalysisDetails(BaseModel):
    status: bool = Field(description="False means an error occured")
    special_status_code: int = Field(description="Special error code, 0 means no special case")
    uuid: str = Field(description="Unique analysis identifier")
    sha256: str = Field(description="String hex encoded input file SHA256")
    sha1: str = Field(description="String hex encoded input file SHA1")
    md5: str = Field(description="String hex encoded input file MD5")
    ssdeep: str = Field(description="File's SSDeep")
    is_malware: bool = Field(description="Analysis verdict, malware or not")
    score: int = Field(description="Highest score given by the services, of all the files in the submission")
    done: bool = Field(description="Analysis status, true if analysis is done")
    timestamp: int = Field(description="Timestamp of the start of analysis in milliseconds")
    file_count: int = Field(description="Amount of file in the submission (input + extracted)")
    duration: int = Field(description="Duration of the analysis in milliseconds")
    filetype: str = Field(description="Type of the file")
    size: int = Field(description="Input file size (in bytes)")

    # non required fields below
    sid: str = Field(
        default=None,
        description="Analysis ID on GLIMPS Malware Expert\ncould be used to construct expert link like:\nhttps://gmalware.useddomain.glimps.re/expert/en/analysis/results/advanced/${SID}",
    )
    token: str = Field(
        default=None,
        description="Token that can be used to view analysis result in expert view",
    )
    error: str = Field(default=None, description="Error message if Status is false")
    errors: dict[str, str] = Field(default=None, description="Error message by services")
    filenames: list[str] = Field(default=None, description="List of analysed filename")
    malwares: list[str] = Field(default=None, description="List of malware names found in analysis")
    files: list[FileResult] = Field(
        default=None,
        description="Array of submission files (input file and extracted sub-files)",
    )
    threats: dict[str, Threat] = Field(
        default=None,
        description="Summary of threats found in submission. Each submission file reaching threshold score will add an entry. Entry keys are files' SHA256",
    )


class AnalysisResponse(BaseModel):
    analysis: AnalysisDetails = Field(..., description="Analysis response details")
    view_url: str = Field(default="", description="Analysis URL")


class ProfileStatus(BaseModel):
    daily_quota: int = Field(description="Number of submissions authorized for the profile within 24h")
    available_daily_quota: int = Field(
        description="Number of submissions still available within 24h. It's a sliding window, so a new slot will be released 24h after each submission"
    )
    cache: bool = Field(description="If True, the profile is configured to use cached result by default")
    estimated_analysis_duration: int = Field(
        description="Estimation of the duration for the next submissions in milliseconds. It's based on the average time of submissions and the submission queue state. The real duration could differ from the estimation"
    )


class ExportSubmissionArguments(BaseModel):
    uuid: str = Field(description="Unique analysis identifier")
    format: str = Field(description="Export format")
    layout: str = Field(description="Export layout")
    is_full: str = Field(default=False, description="Export full analysis or summarized")

    @validator("format")
    def check_format(cls, v: str):
        if v not in EXPORT_FORMATS:
            raise ValueError(f"format must be one of {EXPORT_FORMATS}")
        return v

    @validator("layout")
    def check_layout(cls, v: str):
        if v not in EXPORT_LAYOUTS:
            raise ValueError(f"layout must be one of {EXPORT_LAYOUTS}")
        return v
