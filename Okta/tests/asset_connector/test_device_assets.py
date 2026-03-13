from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.asset_connector.models.ocsf.device import (
    Device,
    DeviceOCSFModel,
    DeviceTypeId,
    DeviceTypeStr,
    OperatingSystem,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.module import Module

from okta_modules.asset_connector.device_assets import OktaDevice, OktaDeviceAssetConnector, OktaDeviceProfile


@pytest.fixture
def test_okta_device_asset_connector(data_storage):
    module = Module()
    module.configuration = {
        "base_url": "https://example.com",
        "apikey": "fake_okta_api_key",
    }

    connector = OktaDeviceAssetConnector(module=module, data_path=data_storage)
    connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60,
    }
    connector.log = Mock()
    connector.log_exception = Mock()

    return connector


# ========================================
# Tests: fetch_next_devices method
# ========================================
@pytest.mark.asyncio
async def test_fetch_next_devices_success(test_okta_device_asset_connector):
    mock_executor = AsyncMock()
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_device = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-01T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="dev",
            platform="windows",
            serialNumber="SN001",
            sid="SID001",
            registered=True,
            secureHardwarePresent=True,
            diskEncryptionType="BitLocker",
            osVersion="10",
            manufacturer="Dell",
            model="Latitude 7420",
        ),
    )

    mock_response.get_type.return_value = lambda body=None: [mock_device]
    mock_response.get_body.return_value = [mock_device.model_dump()]
    mock_executor.create_request = AsyncMock(return_value=(mock_request, None))
    mock_executor.execute = AsyncMock(return_value=(mock_response, None))

    mock_client = MagicMock()
    mock_client.get_request_executor.return_value = mock_executor
    test_okta_device_asset_connector.client = mock_client

    devices, response = await test_okta_device_asset_connector.fetch_next_devices("/api/v1/devices")

    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0].id == "dev1"
    assert response == mock_response


@pytest.mark.asyncio
async def test_fetch_next_devices_error_response(test_okta_device_asset_connector):
    mock_executor = AsyncMock()
    mock_request = MagicMock()
    mock_executor.create_request = AsyncMock(return_value=(mock_request, None))
    mock_executor.execute = AsyncMock(return_value=(None, "Some error"))

    mock_client = MagicMock()
    mock_client.get_request_executor.return_value = mock_executor
    test_okta_device_asset_connector.client = mock_client

    devices, response = await test_okta_device_asset_connector.fetch_next_devices("/api/v1/devices")

    assert devices == []
    assert response is None


@pytest.mark.asyncio
async def test_fetch_next_devices_no_devices(test_okta_device_asset_connector):
    mock_executor = AsyncMock()
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_response.get_type.return_value = lambda body=None: []
    mock_response.get_body.return_value = []
    mock_executor.create_request = AsyncMock(return_value=(mock_request, None))
    mock_executor.execute = AsyncMock(return_value=(mock_response, None))

    mock_client = MagicMock()
    mock_client.get_request_executor.return_value = mock_executor
    test_okta_device_asset_connector.client = mock_client

    devices, response = await test_okta_device_asset_connector.fetch_next_devices("/api/v1/devices")

    assert devices == []
    assert response is None


@pytest.mark.asyncio
async def test_fetch_next_devices_exception(test_okta_device_asset_connector):
    mock_executor = AsyncMock()
    mock_executor.create_request = AsyncMock(side_effect=Exception("Boom"))

    mock_client = MagicMock()
    mock_client.get_request_executor.return_value = mock_executor
    test_okta_device_asset_connector.client = mock_client

    devices, response = await test_okta_device_asset_connector.fetch_next_devices("/api/v1/devices")

    assert devices == []
    assert response is None


# ========================================
# Tests: next_list_devices method
# ========================================
@pytest.mark.asyncio
async def test_next_list_devices_success(test_okta_device_asset_connector):
    # Arrange
    mock_device1 = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-01T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Device 1",
            platform="windows",
            serialNumber="SN001",
            sid="SID001",
            registered=True,
            secureHardwarePresent=True,
            diskEncryptionType="BitLocker",
            osVersion="10.0.19041",
            manufacturer="Dell",
            model="Latitude 7420",
        ),
    )
    mock_device2 = OktaDevice(
        id="dev2",
        status="ACTIVE",
        created="2023-01-02T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Device 2",
            platform="macos",
            serialNumber="SN002",
            sid="SID002",
            registered=True,
            secureHardwarePresent=True,
            diskEncryptionType="FileVault",
            osVersion="13.0",
            manufacturer="Apple",
            model="MacBook Pro",
        ),
    )

    mock_response = MagicMock()
    mock_response.has_next.return_value = False

    with patch.object(test_okta_device_asset_connector, "fetch_next_devices") as mock_fetch:
        mock_fetch.return_value = ([mock_device1, mock_device2], mock_response)

        # Act
        devices = [device async for device in test_okta_device_asset_connector.next_list_devices()]

        # Assert
        assert len(devices) == 2
        assert devices[0].id == "dev1"
        assert devices[1].id == "dev2"
        mock_fetch.assert_called_once_with("/api/v1/devices")


@pytest.mark.asyncio
async def test_next_list_devices_failure(test_okta_device_asset_connector):
    # Arrange
    with patch.object(test_okta_device_asset_connector, "fetch_next_devices") as mock_fetch:
        mock_fetch.side_effect = Exception("API Error")

        # Act & Assert
        with pytest.raises(Exception):
            # Need to consume the generator to trigger the exception
            async for _ in test_okta_device_asset_connector.next_list_devices():
                pass


# ========================================
# Tests: get_device_os method
# ========================================
def test_get_device_os_windows_success(test_okta_device_asset_connector):
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("windows", "10.0.19041")

    assert os.name == "Windows"
    assert os.type == OSTypeStr.WINDOWS
    assert os.type_id == OSTypeId.WINDOWS


def test_get_device_os_macos_success(test_okta_device_asset_connector):
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("macos", "13.0")

    assert os.name == "macOS"
    assert os.type == OSTypeStr.MACOS
    assert os.type_id == OSTypeId.MACOS


def test_get_device_os_linux_success(test_okta_device_asset_connector):
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("linux", "5.4.0")

    assert os.name == "Linux"
    assert os.type == OSTypeStr.LINUX
    assert os.type_id == OSTypeId.LINUX


def test_get_device_os_ios_success(test_okta_device_asset_connector):
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("ios", "16.0")

    assert os.name == "iOS"
    assert os.type == OSTypeStr.IOS
    assert os.type_id == OSTypeId.IOS


def test_get_device_os_android_success(test_okta_device_asset_connector):
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("android", "13")

    assert os.name == "Android"
    assert os.type == OSTypeStr.ANDROID
    assert os.type_id == OSTypeId.ANDROID


def test_get_device_os_unknown_success(test_okta_device_asset_connector):
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("unknown", "1.0")

    assert os.name == "unknown"
    assert os.type == OSTypeStr.OTHER
    assert os.type_id == OSTypeId.OTHER


def test_get_device_os_case_insensitive(test_okta_device_asset_connector):
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("WINDOWS", "10.0.19041")

    assert os.name == "Windows"
    assert os.type == OSTypeStr.WINDOWS


# ========================================
# Tests: get_device_type method
# ========================================
def test_get_device_type_windows_desktop(test_okta_device_asset_connector):
    device_type, device_type_id = test_okta_device_asset_connector.get_device_type("windows")

    assert device_type == DeviceTypeStr.DESKTOP
    assert device_type_id == DeviceTypeId.DESKTOP


def test_get_device_type_macos_desktop(test_okta_device_asset_connector):
    device_type, device_type_id = test_okta_device_asset_connector.get_device_type("macos")

    assert device_type == DeviceTypeStr.DESKTOP
    assert device_type_id == DeviceTypeId.DESKTOP


def test_get_device_type_ios_mobile(test_okta_device_asset_connector):
    device_type, device_type_id = test_okta_device_asset_connector.get_device_type("ios")

    assert device_type == DeviceTypeStr.MOBILE
    assert device_type_id == DeviceTypeId.MOBILE


def test_get_device_type_android_mobile(test_okta_device_asset_connector):
    device_type, device_type_id = test_okta_device_asset_connector.get_device_type("android")

    assert device_type == DeviceTypeStr.MOBILE
    assert device_type_id == DeviceTypeId.MOBILE


def test_get_device_type_linux_other(test_okta_device_asset_connector):
    device_type, device_type_id = test_okta_device_asset_connector.get_device_type("linux")

    assert device_type == DeviceTypeStr.OTHER
    assert device_type_id == DeviceTypeId.OTHER


def test_get_device_type_unknown_other(test_okta_device_asset_connector):
    device_type, device_type_id = test_okta_device_asset_connector.get_device_type("unknown")

    assert device_type == DeviceTypeStr.OTHER
    assert device_type_id == DeviceTypeId.OTHER


def test_get_device_type_case_insensitive(test_okta_device_asset_connector):
    device_type, device_type_id = test_okta_device_asset_connector.get_device_type("WINDOWS")

    assert device_type == DeviceTypeStr.DESKTOP
    assert device_type_id == DeviceTypeId.DESKTOP


# ========================================
# Tests: map_fields method
# ========================================
@pytest.mark.asyncio
async def test_map_fields_success(test_okta_device_asset_connector):
    okta_device = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Test Device",
            platform="windows",
            serialNumber="SN001",
            sid="SID001",
            registered=True,
            secureHardwarePresent=True,
            diskEncryptionType="ALL_INTERNAL_VOLUMES",
            osVersion="10.0.19041",
            manufacturer="Dell",
            model="Latitude 7420",
        ),
    )

    result = await test_okta_device_asset_connector.map_fields(okta_device)

    assert isinstance(result, DeviceOCSFModel)
    assert result.device.hostname == "Test Device"
    assert result.device.uid == "dev1"
    assert result.device.type == DeviceTypeStr.DESKTOP
    assert result.device.type_id == DeviceTypeId.DESKTOP
    assert result.device.os.name == "Windows"
    assert result.device.vendor_name == "Dell"
    assert result.device.model == "Latitude 7420"
    assert result.device.created_time == 1672531200.0
    assert result.device.last_seen_time == 1672617600.0
    assert result.device.is_managed is True
    assert result.device.is_compliant is True
    assert result.activity_name == "Collect"
    assert result.category_name == "Discovery"
    assert result.class_name == "Device Inventory Info"
    assert result.metadata.product.name == "Okta"
    assert result.metadata.product.vendor_name == "Okta"
    assert result.severity == "Informational"
    assert result.enrichments is not None
    assert len(result.enrichments) == 1
    assert result.enrichments[0].name == "device_info"
    assert result.enrichments[0].value == "hardware_and_security"


@pytest.mark.asyncio
async def test_map_fields_failure_invalid_device(test_okta_device_asset_connector):
    invalid_device = {"invalid": "data"}

    with pytest.raises(AttributeError):
        await test_okta_device_asset_connector.map_fields(invalid_device)


# ========================================
# Tests: get_assets method
# ========================================
@pytest.mark.asyncio
async def test_get_assets_success(test_okta_device_asset_connector):

    mock_device1 = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Device 1",
            platform="windows",
            serialNumber="SN001",
            sid="SID001",
            registered=True,
            secureHardwarePresent=True,
            diskEncryptionType="BitLocker",
            osVersion="10.0.19041",
            manufacturer="Dell",
            model="Latitude 7420",
        ),
    )
    mock_device2 = OktaDevice(
        id="dev2",
        status="ACTIVE",
        created="2023-01-02T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Device 2",
            platform="macos",
            serialNumber="SN002",
            sid="SID002",
            registered=True,
            secureHardwarePresent=True,
            diskEncryptionType="FileVault",
            osVersion="13.0",
            manufacturer="Apple",
            model="MacBook Pro",
        ),
    )

    # Mock the _data_path to have an absolute method
    test_okta_device_asset_connector._data_path = MagicMock()
    test_okta_device_asset_connector._data_path.absolute.return_value = "/tmp/test"

    # Create async generator for mocking
    async def mock_next_list_devices():
        yield mock_device1
        yield mock_device2

    with (
        patch.object(test_okta_device_asset_connector, "next_list_devices", mock_next_list_devices),
        patch.object(test_okta_device_asset_connector, "map_fields") as mock_map,
    ):
        mock_map.side_effect = [
            DeviceOCSFModel(
                activity_id=2,
                activity_name="Collect",
                category_name="Discovery",
                category_uid=5,
                class_name="Device Inventory Info",
                class_uid=5001,
                device=Device(
                    hostname="Device 1",
                    uid="dev1",
                    type_id=DeviceTypeId.DESKTOP,
                    type=DeviceTypeStr.DESKTOP,
                    location=None,
                    os=OperatingSystem(name="Windows", type=OSTypeStr.WINDOWS, type_id=OSTypeId.WINDOWS),
                ),
                time=1672531200.0,
                metadata=Metadata(product=Product(name="Okta", vendor_name="Okta", version="N/A"), version="1.6.0"),
                severity="Informational",
                severity_id=1,
                type_name="Software Inventory Info: Collect",
                type_uid=500102,
            ),
            DeviceOCSFModel(
                activity_id=2,
                activity_name="Collect",
                category_name="Discovery",
                category_uid=5,
                class_name="Device Inventory Info",
                class_uid=5001,
                device=Device(
                    hostname="Device 2",
                    uid="dev2",
                    type_id=DeviceTypeId.DESKTOP,
                    type=DeviceTypeStr.DESKTOP,
                    location=None,
                    os=OperatingSystem(name="macOS", type=OSTypeStr.MACOS, type_id=OSTypeId.MACOS),
                ),
                time=1672617600.0,
                metadata=Metadata(product=Product(name="Okta", vendor_name="Okta", version="N/A"), version="1.6.0"),
                severity="Informational",
                severity_id=1,
                type_name="Software Inventory Info: Collect",
                type_uid=500102,
            ),
        ]

        # Act
        assets = [asset async for asset in test_okta_device_asset_connector.get_assets()]

        # Assert
        assert len(assets) == 2
        assert assets[0].device.hostname == "Device 1"
        assert assets[1].device.hostname == "Device 2"
        assert mock_map.call_count == 2


@pytest.mark.asyncio
async def test_get_assets_failure_mapping_error(test_okta_device_asset_connector):
    # Arrange
    mock_device = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-01T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Device 1",
            platform="windows",
            serialNumber="SN001",
            sid="SID001",
            registered=True,
            secureHardwarePresent=True,
            diskEncryptionType="BitLocker",
            osVersion="10.0.19041",
            manufacturer="Dell",
            model="Latitude 7420",
        ),
    )

    # Mock the _data_path to have an absolute method
    test_okta_device_asset_connector._data_path = MagicMock()
    test_okta_device_asset_connector._data_path.absolute.return_value = "/tmp/test"

    # Create async generator for mocking
    async def mock_next_list_devices():
        yield mock_device

    with (
        patch.object(test_okta_device_asset_connector, "next_list_devices", mock_next_list_devices),
        patch.object(test_okta_device_asset_connector, "map_fields") as mock_map,
    ):
        mock_map.side_effect = Exception("Mapping error")

        # Act
        assets = [asset async for asset in test_okta_device_asset_connector.get_assets()]

        # Assert
        assert len(assets) == 0  # Should skip the device with mapping error
        mock_map.assert_called_once()


@pytest.mark.asyncio
async def test_get_assets_failure_no_devices(test_okta_device_asset_connector):
    # Arrange
    # Mock the _data_path to have an absolute method
    test_okta_device_asset_connector._data_path = MagicMock()
    test_okta_device_asset_connector._data_path.absolute.return_value = "/tmp/test"

    # Create empty async generator for mocking
    async def mock_next_list_devices():
        if False:
            yield None

    with patch.object(test_okta_device_asset_connector, "next_list_devices", mock_next_list_devices):
        # Act
        assets = [asset async for asset in test_okta_device_asset_connector.get_assets()]

        # Assert
        assert len(assets) == 0


# ========================================
# Tests: Edge cases and additional scenarios
# ========================================
@pytest.mark.asyncio
async def test_fetch_next_devices_with_query_params(test_okta_device_asset_connector):
    """Test fetch_next_devices with query parameters for date filtering."""
    # Arrange
    mock_executor = AsyncMock()
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_device = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-01T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Test Device",
            platform="windows",
            serialNumber="SN001",
            sid="SID001",
            registered=True,
            secureHardwarePresent=True,
            diskEncryptionType="BitLocker",
            osVersion="10.0.19041",
            manufacturer="Dell",
            model="Latitude 7420",
        ),
    )

    # Mock the response
    mock_response.get_type.return_value = lambda body=None: [mock_device]
    mock_response.get_body.return_value = [mock_device.model_dump()]
    mock_executor.create_request = AsyncMock(return_value=(mock_request, None))
    mock_executor.execute = AsyncMock(return_value=(mock_response, None))

    # Mock the client
    mock_client = MagicMock()
    mock_client.get_request_executor.return_value = mock_executor
    test_okta_device_asset_connector.client = mock_client

    # Mock the context to return a most recent date
    mock_context = MagicMock()
    mock_context.__enter__.return_value = {"most_recent_date_seen": "2023-01-01T00:00:00Z"}
    mock_context.__exit__.return_value = None

    with patch.object(test_okta_device_asset_connector, "context", mock_context):
        # Act
        devices, response = await test_okta_device_asset_connector.fetch_next_devices("/api/v1/devices")

        # Assert
        assert isinstance(devices, list)
        assert len(devices) == 1
        assert devices[0].id == "dev1"
        assert response == mock_response
        # Verify that create_request was called with query parameters
        mock_executor.create_request.assert_called_once()
        call_args = mock_executor.create_request.call_args
        assert "search" in call_args[1]["url"] or "?" in call_args[1]["url"]


@pytest.mark.asyncio
async def test_next_list_devices_with_pagination(test_okta_device_asset_connector):
    """Test next_list_devices with pagination (has_next() returns True)."""
    # Arrange
    mock_device1 = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-01T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Device 1",
            platform="windows",
            serialNumber="SN001",
            sid="SID001",
            registered=True,
            secureHardwarePresent=True,
            diskEncryptionType="BitLocker",
            osVersion="10.0.19041",
            manufacturer="Dell",
            model="Latitude 7420",
        ),
    )
    mock_device2 = OktaDevice(
        id="dev2",
        status="ACTIVE",
        created="2023-01-02T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Device 2",
            platform="macos",
            serialNumber="SN002",
            sid="SID002",
            registered=True,
            secureHardwarePresent=True,
            diskEncryptionType="FileVault",
            osVersion="13.0",
            manufacturer="Apple",
            model="MacBook Pro",
        ),
    )

    mock_response1 = MagicMock()
    mock_response1.has_next.return_value = True
    mock_response1._next = "/api/v1/devices?next=page2"

    mock_response2 = MagicMock()
    mock_response2.has_next.return_value = False

    with patch.object(test_okta_device_asset_connector, "fetch_next_devices") as mock_fetch:
        mock_fetch.side_effect = [
            ([mock_device1], mock_response1),
            ([mock_device2], mock_response2),
        ]

        # Act
        devices = [device async for device in test_okta_device_asset_connector.next_list_devices()]

        # Assert
        assert len(devices) == 2
        assert devices[0].id == "dev1"
        assert devices[1].id == "dev2"
        assert mock_fetch.call_count == 2
        mock_fetch.assert_any_call("/api/v1/devices")
        mock_fetch.assert_any_call("/api/v1/devices?next=page2")


def test_get_device_os_with_none_values(test_okta_device_asset_connector):
    """Test get_device_os with None values for version."""
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("windows", None)

    assert os.name == "Windows"
    assert os.type == OSTypeStr.WINDOWS
    assert os.type_id == OSTypeId.WINDOWS


def test_get_device_os_with_empty_string(test_okta_device_asset_connector):
    """Test get_device_os with empty string for platform."""
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("", "1.0")

    assert os.name == ""
    assert os.type == OSTypeStr.OTHER
    assert os.type_id == OSTypeId.OTHER


@pytest.mark.asyncio
async def test_map_fields_with_minimal_device(test_okta_device_asset_connector):
    """Test map_fields with a device that has minimal profile information."""
    minimal_device = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-01T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Minimal Device",
            platform="unknown",
            registered=False,
            secureHardwarePresent=False,
            osVersion="1.0",
        ),
    )

    result = await test_okta_device_asset_connector.map_fields(minimal_device)

    assert isinstance(result, DeviceOCSFModel)
    assert result.device.hostname == "Minimal Device"
    assert result.device.uid == "dev1"
    assert result.device.type == DeviceTypeStr.OTHER
    assert result.device.type_id == DeviceTypeId.OTHER
    assert result.device.os.name == "unknown"
    assert result.device.os.type == OSTypeStr.OTHER
    assert result.activity_name == "Collect"
    assert result.category_name == "Discovery"
    assert result.class_name == "Device Inventory Info"
    assert result.metadata.product.name == "Okta"
    assert result.metadata.product.vendor_name == "Okta"
    assert result.severity == "Informational"


# ========================================
# Tests: Enrichments and compliance
# ========================================
@pytest.mark.asyncio
async def test_map_fields_with_enrichments(test_okta_device_asset_connector):
    """Test map_fields properly creates enrichments for disk encryption."""
    device_with_encryption = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Encrypted Device",
            platform="windows",
            registered=True,
            secureHardwarePresent=True,
            osVersion="10.0.19041",
            diskEncryptionType="ALL_INTERNAL_VOLUMES",
            manufacturer="Dell",
            model="Latitude 7420",
        ),
    )

    result = await test_okta_device_asset_connector.map_fields(device_with_encryption)

    assert result.enrichments is not None
    assert len(result.enrichments) == 1
    assert result.enrichments[0].name == "device_info"
    assert result.enrichments[0].value == "hardware_and_security"
    assert result.enrichments[0].data.Storage_encryption is not None
    assert "all_internal" in result.enrichments[0].data.Storage_encryption.partitions
    assert result.enrichments[0].data.Storage_encryption.partitions["all_internal"] == "Enabled"


@pytest.mark.asyncio
async def test_map_fields_without_enrichments(test_okta_device_asset_connector):
    """Test map_fields with device that has no enrichable data (no serialNumber, sid, or diskEncryptionType)."""
    device_without_enrichments = OktaDevice(
        id="dev2",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Minimal Device",
            platform="windows",
            registered=True,
            secureHardwarePresent=True,
            osVersion="10.0.19041",
            manufacturer="HP",
            model="EliteBook 840",
            # No serialNumber, sid, or diskEncryptionType
        ),
    )

    result = await test_okta_device_asset_connector.map_fields(device_without_enrichments)

    # secureHardwarePresent creates an enrichment
    assert result.enrichments is not None
    assert len(result.enrichments) == 1
    assert result.enrichments[0].data.Users is not None
    assert "secure_hardware_present:True" in result.enrichments[0].data.Users


@pytest.mark.asyncio
async def test_map_fields_compliance_status(test_okta_device_asset_connector):
    """Test map_fields properly sets compliance status based on device status and registration."""
    inactive_device = OktaDevice(
        id="dev1",
        status="INACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Inactive Device",
            platform="windows",
            registered=True,
            secureHardwarePresent=True,
            osVersion="10.0.19041",
        ),
    )

    result = await test_okta_device_asset_connector.map_fields(inactive_device)

    assert result.device.is_managed is True
    assert result.device.is_compliant is False


@pytest.mark.asyncio
async def test_map_fields_all_encryption_types(test_okta_device_asset_connector):
    """Test map_fields handles different encryption types correctly."""
    # Test USER encryption type
    device_user_encryption = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="User Encrypted Device",
            platform="android",
            registered=True,
            secureHardwarePresent=True,
            osVersion="13",
            diskEncryptionType="USER",
        ),
    )

    result = await test_okta_device_asset_connector.map_fields(device_user_encryption)

    assert result.device.type == DeviceTypeStr.MOBILE
    assert result.device.type_id == DeviceTypeId.MOBILE
    assert result.enrichments is not None
    assert len(result.enrichments) == 1
    assert "user" in result.enrichments[0].data.Storage_encryption.partitions
    assert result.enrichments[0].data.Storage_encryption.partitions["user"] == "Enabled"

    # Test FULL encryption type
    device_full_encryption = OktaDevice(
        id="dev2",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Fully Encrypted Device",
            platform="macos",
            registered=True,
            secureHardwarePresent=True,
            osVersion="13.0",
            diskEncryptionType="FULL",
        ),
    )

    result = await test_okta_device_asset_connector.map_fields(device_full_encryption)

    assert result.device.type == DeviceTypeStr.DESKTOP
    assert result.device.type_id == DeviceTypeId.DESKTOP
    assert result.enrichments is not None
    assert len(result.enrichments) == 1
    assert "full" in result.enrichments[0].data.Storage_encryption.partitions
    assert result.enrichments[0].data.Storage_encryption.partitions["full"] == "Enabled"


@pytest.mark.asyncio
async def test_map_fields_with_hardware_enrichment(test_okta_device_asset_connector):
    """Test map_fields creates enrichment for unmapped hardware fields."""
    device_with_hardware = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Device with Hardware Info",
            platform="windows",
            registered=True,
            secureHardwarePresent=True,
            osVersion="10.0.19041",
            serialNumber="SN123456789",
            sid="S-1-5-21-3623811015-3361044348-30300820-1013",
        ),
    )

    result = await test_okta_device_asset_connector.map_fields(device_with_hardware)

    assert result.device.type == DeviceTypeStr.DESKTOP
    assert result.device.type_id == DeviceTypeId.DESKTOP
    assert result.enrichments is not None
    assert len(result.enrichments) == 1
    assert result.enrichments[0].name == "device_info"
    assert result.enrichments[0].value == "hardware_and_security"
    # Hardware info stored in Users field as key:value strings
    assert result.enrichments[0].data.Users is not None
    assert "serial_number:SN123456789" in result.enrichments[0].data.Users
    assert "windows_sid:S-1-5-21-3623811015-3361044348-30300820-1013" in result.enrichments[0].data.Users
    assert "secure_hardware_present:True" in result.enrichments[0].data.Users


@pytest.mark.asyncio
async def test_map_fields_with_combined_enrichment(test_okta_device_asset_connector):
    """Test map_fields creates combined enrichment with both encryption and hardware data."""
    device_with_both = OktaDevice(
        id="dev1",
        status="ACTIVE",
        created="2023-01-01T00:00:00Z",
        lastUpdated="2023-01-02T00:00:00Z",
        profile=OktaDeviceProfile(
            displayName="Device with Full Info",
            platform="windows",
            registered=True,
            secureHardwarePresent=False,
            osVersion="10.0.19041",
            serialNumber="SN987654321",
            diskEncryptionType="ALL_INTERNAL_VOLUMES",
        ),
    )

    result = await test_okta_device_asset_connector.map_fields(device_with_both)

    assert result.device.type == DeviceTypeStr.DESKTOP
    assert result.device.type_id == DeviceTypeId.DESKTOP
    assert result.enrichments is not None
    assert len(result.enrichments) == 1

    # Check combined enrichment
    enrichment = result.enrichments[0]
    assert enrichment.name == "device_info"
    assert enrichment.value == "hardware_and_security"

    # Check encryption data
    assert enrichment.data.Storage_encryption is not None
    assert "all_internal" in enrichment.data.Storage_encryption.partitions
    assert enrichment.data.Storage_encryption.partitions["all_internal"] == "Enabled"

    # Check hardware data
    assert enrichment.data.Users is not None
    assert "serial_number:SN987654321" in enrichment.data.Users
    assert "secure_hardware_present:False" in enrichment.data.Users
