from unittest.mock import patch, MagicMock
import vt
from googlethreatintelligence.get_ioc_report import GTIIoCReport


API_KEY = "FAKE_API_KEY"
DOMAIN = "example.com"
IP = "8.8.8.8"
URL = "http://malicious.example.com"
FILE_HASH = "44d88612fea8a8f36de82e1278abb02f"


@patch("googlethreatintelligence.get_ioc_report.VTAPIConnector")
@patch("googlethreatintelligence.get_ioc_report.vt.Client")
def test_get_ioc_report_success(mock_vt_client, mock_connector):
    """Test successful IoC report retrieval for a domain"""
    # Mock VTAPIConnector behavior
    mock_connector_instance = MagicMock()
    mock_connector.return_value = mock_connector_instance

    # Mock a result object returned by the connector
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    mock_result.response = {"indicator": DOMAIN, "malicious": True}
    mock_result.error = None

    mock_connector_instance.results = [mock_result]

    # Mock vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Action setup
    action = GTIIoCReport()
    action.module.configuration = {"api_key": API_KEY}

    # Run the action
    response = action.run({"domain": DOMAIN})

    # Verify output
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is True
    assert "data" in response
    assert response["data"]["indicator"] == DOMAIN

    # Verify vt.Client was instantiated correctly
    mock_vt_client.assert_called_once_with(API_KEY)

    # Verify VTAPIConnector was instantiated with expected arguments
    mock_connector.assert_called_once_with(
        API_KEY,
        domain=DOMAIN,
        ip="",
        url="",
        file_hash=""
    )

    # Ensure get_ioc_report was called with the VT client
    mock_connector_instance.get_ioc_report.assert_called_once_with(mock_client_instance)


@patch("googlethreatintelligence.get_ioc_report.VTAPIConnector")
@patch("googlethreatintelligence.get_ioc_report.vt.Client")
def test_get_ioc_report_fail_api_error(mock_vt_client, mock_connector):
    """Test handling when VT API raises vt.APIError"""
    # Mock vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Mock connector to raise APIError when called
    mock_connector_instance = MagicMock()
    mock_connector.return_value = mock_connector_instance
    mock_connector_instance.get_ioc_report.side_effect = vt.APIError("SomeAPIError", "Internal Server Error")

    # Action setup
    action = GTIIoCReport()
    action.module.configuration = {"api_key": API_KEY}

    # Run the action
    response = action.run({"domain": DOMAIN})

    # Verify error response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is False
    assert "error" in response
    assert "Internal Server Error" in response["error"]

    # Verify vt.Client and VTAPIConnector were both called
    mock_vt_client.assert_called_once_with(API_KEY)
    mock_connector.assert_called_once()


def test_get_ioc_report_no_api_key():
    """Test error handling when API key is missing"""
    action = GTIIoCReport()
    action.module.configuration = {}
