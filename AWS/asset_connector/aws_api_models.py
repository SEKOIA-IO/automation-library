"""Pydantic models for raw AWS IAM API responses."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AwsApiUser(BaseModel):
    """Raw AWS IAM user object returned by ``iam:ListUsers``."""

    Path: Optional[str] = None
    UserName: Optional[str] = None
    UserId: Optional[str] = None
    Arn: Optional[str] = None
    CreateDate: Optional[datetime] = None
    PasswordLastUsed: Optional[datetime] = Field(default=None)


class AwsApiUserGroup(BaseModel):
    """Raw AWS IAM group object returned by ``iam:ListGroupsForUser``."""

    Path: Optional[str] = None
    GroupName: Optional[str] = None
    GroupId: Optional[str] = None
    Arn: Optional[str] = None
    CreateDate: Optional[datetime] = None


class AwsApiBlockDeviceMappingEbs(BaseModel):
    AttachTime: Optional[datetime] = None


class AwsApiBlockDeviceMapping(BaseModel):
    Ebs: Optional[AwsApiBlockDeviceMappingEbs] = None


class AwsApiTag(BaseModel):
    Key: Optional[str] = None
    Value: Optional[str] = None


class AwsApiNetworkInterface(BaseModel):
    NetworkInterfaceId: Optional[str] = None
    Description: Optional[str] = None
    MacAddress: Optional[str] = None
    PrivateIpAddress: Optional[str] = None
    PrivateDnsName: Optional[str] = None


class AwsApiSecurityGroup(BaseModel):
    GroupId: Optional[str] = None
    GroupName: Optional[str] = None


class AwsApiPlacement(BaseModel):
    AvailabilityZone: Optional[str] = None


class AwsApiInstanceState(BaseModel):
    Name: Optional[str] = None


class AwsApiInstance(BaseModel):
    """Raw AWS EC2 instance object returned by ``ec2:DescribeInstances``."""

    InstanceId: Optional[str] = None
    BlockDeviceMappings: Optional[List[AwsApiBlockDeviceMapping]] = Field(default_factory=list)
    LaunchTime: Any = None
    PublicDnsName: Optional[str] = None
    PrivateDnsName: Optional[str] = None
    Tags: Optional[List[AwsApiTag]] = Field(default_factory=list)
    NetworkInterfaces: Optional[List[AwsApiNetworkInterface]] = Field(default_factory=list)
    SecurityGroups: Optional[List[AwsApiSecurityGroup]] = Field(default_factory=list)
    PublicIpAddress: Optional[str] = None
    PrivateIpAddress: Optional[str] = None
    Placement: Optional[AwsApiPlacement] = None
    SubnetId: Optional[str] = None
    VpcId: Optional[str] = None
    Hypervisor: Optional[str] = None
    InstanceType: Optional[str] = None
    ImageId: Optional[str] = None
    State: Optional[AwsApiInstanceState] = None
    IamInstanceProfile: Optional[Dict[str, Any]] = None
    PlatformDetails: Optional[str] = None


class AwsReservationApi(BaseModel):
    """Raw AWS EC2 reservation object returned by ``ec2:DescribeInstances``."""

    ReservationId: Optional[str] = None
    OwnerId: Optional[str] = None
    Instances: Optional[List[AwsApiInstance]] = Field(default_factory=list)
