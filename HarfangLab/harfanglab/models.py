# coding: utf-8
"""
Data models of the HarfangLab module
"""

# natives
from typing import Any, List

# third parties
from pydantic.v1 import BaseModel


class JobTarget(BaseModel):
    agent_ids: list[str] | None = None
    group_ids: list[str] | None = None


class JobAction(BaseModel):
    value: str  # job action identifier (eg: getPipeList, downloadFile, etc.)
    params: Any

    def as_params(self) -> dict[str, Any]:
        return {
            self.value: self.params,
        }


class JobTriggerResult(BaseModel):
    id: str  # job's id
    action: str  # job action identifier (eg: getPipeList, downloadFile, etc.)
    creationtime: str
    parameters: Any


class JobStatus(BaseModel):

    total: int  # number of job actions to be executed

    # status when running (in exec-time order)
    waiting: int
    running: int
    injecting: int

    # status when ended
    done: int
    error: int
    canceled: int

    def is_running(self) -> bool:
        return (self.waiting + self.running + self.injecting) > 0


class JobBatchInformation(BaseModel):
    status: JobStatus


class HostnameEntry(BaseModel):
    hostname: str
    ipaddress: str
    lastseen: str
    ostype: str
    status: str


class HostnamesResult(BaseModel):
    hostnames: List[HostnameEntry]
