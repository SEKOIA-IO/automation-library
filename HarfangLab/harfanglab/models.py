# coding: utf-8
"""
Data models of the HarfangLab module
"""

# natives
import time
from typing import Any, Dict, List, Optional

# third parties
from pydantic import BaseModel, Field


class JobTarget(BaseModel):
    agents: List[str]
    groups: List[str]


class JobAction(BaseModel):
    label: str  # name of the job in the EDR instance
    value: str  # job action identifier (eg: getPipeList, downloadFile, etc.)
    params: Optional[Dict[str, Any]]
    isValid: bool = True
    id: int = Field(default_factory=lambda: int(time.time() * 1000))


class JobTriggerResult(BaseModel):
    id: str  # job's id
    action: str  # job action identifier (eg: getPipeList, downloadFile, etc.)
    creationtime: str
    parameters: Optional[Dict[str, Any]]


class JobStatus(BaseModel):

    instance: int  # number of job actions to be executed

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


class HostnameEntry(BaseModel):
    hostname: str
    ipaddress: str
    lastseen: str
    ostype: str
    status: str


class HostnamesResult(BaseModel):
    hostnames: List[HostnameEntry]
