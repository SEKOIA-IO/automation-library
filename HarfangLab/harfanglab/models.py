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
    label: str
    value: str
    params: Optional[Dict[str, Any]]
    isValid: bool = True
    id: int = Field(default_factory=lambda: int(time.time() * 1000))


class JobTriggerResult(BaseModel):
    id: str
    action: str
    creationtime: str
    parameters: Optional[Dict[str, Any]]


class HostnameEntry(BaseModel):
    hostname: str
    ipaddress: str
    lastseen: Field(..., alias="lastseen")
    ostype: Field(..., alias="ostype")
    status: str


class HostnamesResult(BaseModel):
    hostnames: List[HostnameEntry]
