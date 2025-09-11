import pytest
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from sekoia_automation.asset_connector.models.ocsf.device import (
    DeviceOCSFModel,
    Device,
    OperatingSystem,
    DeviceTypeId,
    DeviceTypeStr,
    OSTypeId,
    OSTypeStr,
)
from sekoia_automation.asset_connector.models.ocsf.base import Metadata, Product
from sekoia_automation.module import Module
from okta_modules.asset_connector.device_assets import OktaDeviceAssetConnector, OktaDevice, OktaDeviceProfile


@pytest.fixture
def test_okta_device_asset_connector(data_storage):
    module = Module()
    module.configuration = {
        "base_url": "https://example.com",
        "apikey": "fake_okta_api_key",
    }

    test_okta_device_asset_connector = OktaDeviceAssetConnector(module=module, data_path=data_storage)
    test_okta_device_asset_connector.configuration = {
        "sekoia_base_url": "https://sekoia.io",
        "sekoia_api_key": "fake_api_key",
        "frequency": 60,
    }

    test_okta_device_asset_connector.log = Mock()
    test_okta_device_asset_connector.log_exception = Mock()

    yield test_okta_device_asset_connector


# Tests for fetch_next_devices method
@pytest.mark.asyncio
async def test_fetch_next_devices_success(test_okta_device_asset_connector):
    # Arrange
    mock_executor = AsyncMock()  # Make this AsyncMock too
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
        ),
    )

    # Mock the response properly - get_type() returns a function that takes body as parameter
    mock_response.get_type.return_value = lambda body=None: [mock_device]
    mock_response.get_body.return_value = [mock_device.model_dump()]

    mock_executor.create_request = AsyncMock(return_value=(mock_request, None))
    mock_executor.execute = AsyncMock(return_value=(mock_response, None))

    # Mock the client to return the executor directly (not as a coroutine)
    mock_client = MagicMock()
    mock_client.get_request_executor.return_value = mock_executor
    test_okta_device_asset_connector.client = mock_client

    # Act
    devices, response = await test_okta_device_asset_connector.fetch_next_devices("/api/v1/devices")

    # Assert
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0].id == "dev1"
    assert response == mock_response


@pytest.mark.asyncio
async def test_fetch_next_devices_error_response(test_okta_device_asset_connector):
    # Arrange
    mock_executor = AsyncMock()
    mock_request = MagicMock()
    mock_executor.create_request = AsyncMock(return_value=(mock_request, None))
    mock_executor.execute = AsyncMock(return_value=(None, "Some error"))
    # Mock the client to return the executor directly (not as a coroutine)
    mock_client = MagicMock()
    mock_client.get_request_executor.return_value = mock_executor
    test_okta_device_asset_connector.client = mock_client

    # Act
    devices, response = await test_okta_device_asset_connector.fetch_next_devices("/api/v1/devices")

    # Assert
    assert devices == []  # When there's an error, it returns empty list
    assert response is None


@pytest.mark.asyncio
async def test_fetch_next_devices_no_devices(test_okta_device_asset_connector):
    # Arrange
    mock_executor = AsyncMock()
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_response.get_type.return_value = lambda body=None: []
    mock_response.get_body.return_value = []
    mock_executor.create_request = AsyncMock(return_value=(mock_request, None))
    mock_executor.execute = AsyncMock(return_value=(mock_response, None))
    # Mock the client to return the executor directly (not as a coroutine)
    mock_client = MagicMock()
    mock_client.get_request_executor.return_value = mock_executor
    test_okta_device_asset_connector.client = mock_client

    # Act
    devices, response = await test_okta_device_asset_connector.fetch_next_devices("/api/v1/devices")

    # Assert
    assert devices == []  # When devices is empty, it returns empty list
    assert response is None


@pytest.mark.asyncio
async def test_fetch_next_devices_exception(test_okta_device_asset_connector):
    # Arrange
    mock_executor = AsyncMock()
    mock_executor.create_request = AsyncMock(side_effect=Exception("Boom"))
    # Mock the client to return the executor directly (not as a coroutine)
    mock_client = MagicMock()
    mock_client.get_request_executor.return_value = mock_executor
    test_okta_device_asset_connector.client = mock_client

    # Act
    devices, response = await test_okta_device_asset_connector.fetch_next_devices("/api/v1/devices")

    # Assert
    assert devices == []
    assert response is None


# Tests for next_list_devices method
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
        ),
    )

    mock_response = MagicMock()
    mock_response.has_next.return_value = False

    with patch.object(test_okta_device_asset_connector, "fetch_next_devices") as mock_fetch:
        mock_fetch.return_value = ([mock_device1, mock_device2], mock_response)

        # Act
        devices = await test_okta_device_asset_connector.next_list_devices()

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
            await test_okta_device_asset_connector.next_list_devices()


# Tests for get_device_os method
def test_get_device_os_windows_success(test_okta_device_asset_connector):
    # Act
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("windows", "10.0.19041")

    # Assert
    assert os.name == "Windows"
    assert os.type == OSTypeStr.WINDOWS
    assert os.type_id == OSTypeId.WINDOWS


def test_get_device_os_macos_success(test_okta_device_asset_connector):
    # Act
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("macos", "13.0")

    # Assert
    assert os.name == "macOS"
    assert os.type == OSTypeStr.MACOS
    assert os.type_id == OSTypeId.MACOS


def test_get_device_os_linux_success(test_okta_device_asset_connector):
    # Act
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("linux", "5.4.0")

    # Assert
    assert os.name == "Linux"
    assert os.type == OSTypeStr.LINUX
    assert os.type_id == OSTypeId.LINUX


def test_get_device_os_ios_success(test_okta_device_asset_connector):
    # Act
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("ios", "16.0")

    # Assert
    assert os.name == "iOS"
    assert os.type == OSTypeStr.IOS
    assert os.type_id == OSTypeId.IOS


def test_get_device_os_android_success(test_okta_device_asset_connector):
    # Act
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("android", "13")

    # Assert
    assert os.name == "Android"
    assert os.type == OSTypeStr.ANDROID
    assert os.type_id == OSTypeId.ANDROID


def test_get_device_os_unknown_success(test_okta_device_asset_connector):
    # Act
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("unknown", "1.0")

    # Assert
    assert os.name == "unknown"
    assert os.type == OSTypeStr.OTHER
    assert os.type_id == OSTypeId.OTHER


def test_get_device_os_case_insensitive(test_okta_device_asset_connector):
    # Act
    os: OperatingSystem = test_okta_device_asset_connector.get_device_os("WINDOWS", "10.0.19041")

    # Assert
    assert os.name == "Windows"
    assert os.type == OSTypeStr.WINDOWS


# Tests for map_fields method
@pytest.mark.asyncio
async def test_map_fields_success(test_okta_device_asset_connector):
    # Arrange
    # Create a proper OktaDevice object
    okta_device = OktaDevice(
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
        ),
    )

    # Act
    result = await test_okta_device_asset_connector.map_fields(okta_device)

    # Assert
    assert isinstance(result, DeviceOCSFModel)
    assert result.device.hostname == "Test Device"
    assert result.device.uid == "dev1"
    assert result.device.type == DeviceTypeStr.OTHER
    assert result.device.type_id == DeviceTypeId.OTHER
    assert result.device.os.name == "Windows"
    assert result.activity_name == "Collect"
    assert result.category_name == "Discovery"
    assert result.class_name == "Device Inventory Info"
    assert result.metadata.product.name == "Okta"
    assert result.metadata.product.vendor_name == "Okta"
    assert result.severity == "Informational"


@pytest.mark.asyncio
async def test_map_fields_failure_invalid_device(test_okta_device_asset_connector):
    # Arrange
    invalid_device = {"invalid": "data"}

    # Act & Assert
    with pytest.raises(AttributeError):  # dict object has no attribute 'profile'
        await test_okta_device_asset_connector.map_fields(invalid_device)


# Tests for get_assets method
def test_get_assets_success(test_okta_device_asset_connector):
    # Arrange
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
        ),
    )

    # Mock the _data_path to have an absolute method
    test_okta_device_asset_connector._data_path = MagicMock()
    test_okta_device_asset_connector._data_path.absolute.return_value = "/tmp/test"

    with (
        patch.object(test_okta_device_asset_connector, "next_list_devices") as mock_next_list,
        patch.object(test_okta_device_asset_connector, "map_fields") as mock_map,
    ):
        mock_next_list.return_value = [mock_device1, mock_device2]
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
                    type_id=DeviceTypeId.OTHER,
                    type=DeviceTypeStr.OTHER,
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
                    type_id=DeviceTypeId.OTHER,
                    type=DeviceTypeStr.OTHER,
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
        assets = list(test_okta_device_asset_connector.get_assets())

        # Assert
        assert len(assets) == 2
        assert assets[0].device.hostname == "Device 1"
        assert assets[1].device.hostname == "Device 2"
        mock_next_list.assert_called_once()
        assert mock_map.call_count == 2


def test_get_assets_failure_mapping_error(test_okta_device_asset_connector):
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
        ),
    )

    # Mock the _data_path to have an absolute method
    test_okta_device_asset_connector._data_path = MagicMock()
    test_okta_device_asset_connector._data_path.absolute.return_value = "/tmp/test"

    with (
        patch.object(test_okta_device_asset_connector, "next_list_devices") as mock_next_list,
        patch.object(test_okta_device_asset_connector, "map_fields") as mock_map,
    ):
        mock_next_list.return_value = [mock_device]
        mock_map.side_effect = Exception("Mapping error")

        # Act
        assets = list(test_okta_device_asset_connector.get_assets())

        # Assert
        assert len(assets) == 0  # Should skip the device with mapping error
        mock_next_list.assert_called_once()
        mock_map.assert_called_once()


def test_get_assets_failure_no_devices(test_okta_device_asset_connector):
    # Arrange
    # Mock the _data_path to have an absolute method
    test_okta_device_asset_connector._data_path = MagicMock()
    test_okta_device_asset_connector._data_path.absolute.return_value = "/tmp/test"

    with patch.object(test_okta_device_asset_connector, "next_list_devices") as mock_next_list:
        mock_next_list.return_value = []

        # Act
        assets = list(test_okta_device_asset_connector.get_assets())

        # Assert
        assert len(assets) == 0
        mock_next_list.assert_called_once()


# Additional tests for fetch_next_devices edge cases
@pytest.mark.asyncio
async def test_fetch_next_devices_success_with_response(test_okta_device_asset_connector):
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
        ),
    )
    # Mock the response properly - get_type() returns a function that takes body as parameter
    mock_response.get_type.return_value = lambda body=None: [mock_device]
    mock_response.get_body.return_value = [mock_device.model_dump()]
    mock_executor.create_request = AsyncMock(return_value=(mock_request, None))
    mock_executor.execute = AsyncMock(return_value=(mock_response, None))
    # Mock the client to return the executor directly (not as a coroutine)
    mock_client = MagicMock()
    mock_client.get_request_executor.return_value = mock_executor
    test_okta_device_asset_connector.client = mock_client

    # Act
    devices, response = await test_okta_device_asset_connector.fetch_next_devices("/api/v1/devices")

    # Assert
    assert isinstance(devices, list)
    assert len(devices) == 1
    assert devices[0].id == "dev1"
    assert response == mock_response


@pytest.mark.asyncio
async def test_fetch_next_devices_success_empty_list(test_okta_device_asset_connector):
    # Arrange
    mock_executor = AsyncMock()
    mock_request = MagicMock()
    mock_response = MagicMock()
    mock_response.get_type.return_value = lambda body=None: []
    mock_response.get_body.return_value = []
    mock_executor.create_request = AsyncMock(return_value=(mock_request, None))
    mock_executor.execute = AsyncMock(return_value=(mock_response, None))
    # Mock the client to return the executor directly (not as a coroutine)
    mock_client = MagicMock()
    mock_client.get_request_executor.return_value = mock_executor
    test_okta_device_asset_connector.client = mock_client

    # Act
    devices, response = await test_okta_device_asset_connector.fetch_next_devices("/api/v1/devices")

    # Assert
    assert devices == []  # When devices is empty, it returns empty list
    assert response is None
