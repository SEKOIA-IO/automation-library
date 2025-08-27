import pytz
import boto3
from collections.abc import Generator

from datetime import datetime
from dateutil.parser import isoparse

from sekoia_automation.storage import PersistentJSON

from sekoia_automation.asset_connector import AssetConnector
from sekoia_automation.asset_connector.models.ocsf.base import (
    Metadata,
    Product,
)
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    Device,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
    DeviceTypeId,
    DeviceTypeStr,
)


class AwsDevice:
    def __init__(self, device: Device, date: datetime):
        self.device = device
        self.date = date


class AwsDeviceAssetConnector(AssetConnector):
    PRODUCT_NAME: str = "AWS EC2"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = PersistentJSON("context.json", self._data_path)

    @property
    def most_recent_date_seen(self) -> str | None:
        with self.context as cache:
            most_recent_date_seen = cache.get("most_recent_date_seen", None)

            return most_recent_date_seen

    def client(self):
        session = boto3.Session(
            aws_access_key_id=self.module.configuration["aws_access_key"],
            aws_secret_access_key=self.module.configuration["aws_secret_access_key"],
            region_name=self.module.configuration["aws_region_name"],
        )
        return session.client("ec2")

    def get_device_os(self, platform_details: str) -> OperatingSystem:
        if "Windows" in platform_details:
            return OperatingSystem(name="Windows", type=OSTypeStr.WINDOWS, type_id=OSTypeId.WINDOWS)
        if "Linux" in platform_details:
            return OperatingSystem(name="Linux", type=OSTypeStr.LINUX, type_id=OSTypeId.LINUX)
        if "MacOS" in platform_details:
            return OperatingSystem(name="MacOS", type=OSTypeStr.MACOS, type_id=OSTypeId.MACOS)
        return OperatingSystem(name=platform_details, type=OSTypeStr.UNKNOWN, type_id=OSTypeId.UNKNOWN)

    def get_aws_devices(self) -> Generator[list[AwsDevice], None, None]:
        self.log("Start fetching AWS devices...", level="info")
        paginator = self.client().get_paginator("describe_instances")
        page_iterator = paginator.paginate()
        date_filter: datetime | None = isoparse(self.most_recent_date_seen) if self.most_recent_date_seen else None
        for page in page_iterator:
            devices = []
            for reservation in page["Reservations"]:
                for instance in reservation["Instances"]:
                    created_time: datetime = instance["BlockDeviceMappings"][0]["Ebs"]["AttachTime"]
                    created_time = created_time.replace(tzinfo=pytz.UTC)
                    if date_filter and (created_time < date_filter):
                        continue
                    device_obj = Device(
                        type_id=DeviceTypeId.SERVER,
                        type=DeviceTypeStr.SERVER,
                        uid=instance["InstanceId"],
                        hostname=instance["PublicDnsName"],
                        os=self.get_device_os(instance["PlatformDetails"]),
                        location=None,
                    )
                    self.log(f"Fetched device: {device_obj.hostname}", level="debug")
                    devices.append(AwsDevice(device=device_obj, date=created_time))
            yield devices

    def get_assets(self) -> Generator[DeviceOCSFModel, None, None]:
        self.log("Start the getting assets generator...", level="info")
        self.log(f"The data path is: {self._data_path.absolute()}", level="info")
        new_most_recent_date = datetime.now().replace(tzinfo=pytz.UTC).isoformat()
        for aws_devices in self.get_aws_devices():
            for aws_device in aws_devices:
                product = Product(name=self.PRODUCT_NAME, version="1.0.0")
                metadata = Metadata(product=product, version="1.6.0")
                device_ocsf = DeviceOCSFModel(
                    activity_id=2,
                    activity_name="Collect",
                    category_name="Discovery",
                    category_uid=5,
                    class_name="Device Inventory Info",
                    class_uid=5001,
                    type_name="Device Inventory Info: Collect",
                    severity="Informational",
                    severity_id=1,
                    type_uid=500102,
                    time=aws_device.date.timestamp(),
                    metadata=metadata,
                    device=aws_device.device,
                )
                yield device_ocsf
        with self.context as cache:
            cache["most_recent_date_seen"] = new_most_recent_date
