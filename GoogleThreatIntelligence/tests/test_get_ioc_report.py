from unittest.mock import patch, MagicMock, PropertyMock
import vt
from googlethreatintelligence.get_ioc_report import GTIIoCReport

# === Test constants ===
API_KEY = "FAKE_API_KEY"
DOMAIN = "google.com"
IP = "8.8.8.8"
URL = "https://www.sekoia.io"
FILE_HASH = "44d88612fea8a8f36de82e1278abb02f"


@patch('googlethreatintelligence.get_ioc_report.vt.Client')
@patch('googlethreatintelligence.get_ioc_report.VTAPIConnector')
def test_get_domain_report_success(mock_connector_class, mock_vt_client):
    """Test successful retrieval of domain report"""
    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance
    
    # Mock VTAPIConnector instance
    mock_connector = MagicMock()
    mock_connector_class.return_value = mock_connector
    
    # Create a mock result
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    mock_result.response = {
        "entity_type": "domains",
        "entity": DOMAIN,
        "id": DOMAIN,
        "reputation": 100,
        "last_analysis_stats": {"malicious": 0, "suspicious": 0, "clean": 80}
    }
    mock_result.error = None
    mock_connector.results = [mock_result]
    
    # Setup action
    action = GTIIoCReport()
    action.module.configuration = {"api_key": API_KEY}
    
    # Run the action
    response = action.run({"domain": DOMAIN})
    
    # Verify response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is True
    assert "data" in response
    assert response["data"]["entity"] == DOMAIN
    assert response["data"]["entity_type"] == "domains"
    
    # Verify VTAPIConnector was called correctly
    mock_connector_class.assert_called_once_with(
        API_KEY, domain=DOMAIN, ip="", url="", file_hash=""
    )
    
    # Verify get_domain_report was called
    mock_connector.get_domain_report.assert_called_once_with(mock_client_instance)
    
    # Verify vt.Client was called with the correct API key
    mock_vt_client.assert_called_once_with(API_KEY)


@patch('googlethreatintelligence.get_ioc_report.vt.Client')
@patch('googlethreatintelligence.get_ioc_report.VTAPIConnector')
def test_get_ip_report_success(mock_connector_class, mock_vt_client):
    """Test successful retrieval of IP report"""
    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance
    
    # Mock VTAPIConnector instance
    mock_connector = MagicMock()
    mock_connector_class.return_value = mock_connector
    
    # Create a mock result
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    mock_result.response = {
        "entity_type": "ip_addresses",
        "entity": IP,
        "id": IP,
        "reputation": 95,
        "country": "US"
    }
    mock_result.error = None
    mock_connector.results = [mock_result]
    
    # Setup action
    action = GTIIoCReport()
    action.module.configuration = {"api_key": API_KEY}
    
    # Run the action
    response = action.run({"ip": IP})
    
    # Verify response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is True
    assert "data" in response
    assert response["data"]["entity"] == IP
    
    # Verify VTAPIConnector was called correctly
    mock_connector_class.assert_called_once_with(
        API_KEY, domain="", ip=IP, url="", file_hash=""
    )
    
    # Verify get_ip_report was called
    mock_connector.get_ip_report.assert_called_once_with(mock_client_instance)


@patch('googlethreatintelligence.get_ioc_report.vt.Client')
@patch('googlethreatintelligence.get_ioc_report.VTAPIConnector')
def test_get_url_report_success(mock_connector_class, mock_vt_client):
    """Test successful retrieval of URL report"""
    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance
    
    # Mock VTAPIConnector instance
    mock_connector = MagicMock()
    mock_connector_class.return_value = mock_connector
    
    # Create a mock result
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    mock_result.response = {
        "entity_type": "urls",
        "entity": URL,
        "last_analysis_stats": {"malicious": 0, "suspicious": 0, "clean": 75}
    }
    mock_result.error = None
    mock_connector.results = [mock_result]
    
    # Setup action
    action = GTIIoCReport()
    action.module.configuration = {"api_key": API_KEY}
    
    # Run the action
    response = action.run({"url": URL})
    
    # Verify response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is True
    assert "data" in response
    
    # Verify VTAPIConnector was called correctly
    mock_connector_class.assert_called_once_with(
        API_KEY, domain="", ip="", url=URL, file_hash=""
    )
    
    # Verify get_url_report was called
    mock_connector.get_url_report.assert_called_once_with(mock_client_instance)


@patch('googlethreatintelligence.get_ioc_report.vt.Client')
@patch('googlethreatintelligence.get_ioc_report.VTAPIConnector')
def test_get_file_report_success(mock_connector_class, mock_vt_client):
    """Test successful retrieval of file report"""
    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance
    
    # Mock VTAPIConnector instance
    mock_connector = MagicMock()
    mock_connector_class.return_value = mock_connector
    
    # Create a mock result
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    mock_result.response = {
        "entity_type": "files",
        "entity": FILE_HASH,
        "id": FILE_HASH,
        "last_analysis_stats": {"malicious": 60, "suspicious": 5, "clean": 0}
    }
    mock_result.error = None
    mock_connector.results = [mock_result]
    
    # Setup action
    action = GTIIoCReport()
    action.module.configuration = {"api_key": API_KEY}
    
    # Run the action
    response = action.run({"file_hash": FILE_HASH})
    
    # Verify response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is True
    assert "data" in response
    assert response["data"]["entity"] == FILE_HASH
    
    # Verify VTAPIConnector was called correctly
    mock_connector_class.assert_called_once_with(
        API_KEY, domain="", ip="", url="", file_hash=FILE_HASH
    )
    
    # Verify get_file_report was called
    mock_connector.get_file_report.assert_called_once_with(mock_client_instance)


@patch('googlethreatintelligence.get_ioc_report.vt.Client')
@patch('googlethreatintelligence.get_ioc_report.VTAPIConnector')
def test_get_ioc_report_api_error(mock_connector_class, mock_vt_client):
    """Test error handling when API fails"""
    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance
    
    # Mock VTAPIConnector instance
    mock_connector = MagicMock()
    mock_connector_class.return_value = mock_connector
    
    # Create a mock error result
    mock_result = MagicMock()
    mock_result.status = "ERROR"
    mock_result.response = None
    mock_result.error = "WrongCredentialsError: Invalid API key"
    mock_connector.results = [mock_result]
    
    # Setup action
    action = GTIIoCReport()
    action.module.configuration = {"api_key": API_KEY}
    
    # Run the action
    response = action.run({"domain": DOMAIN})
    
    # Verify error response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is False
    assert "error" in response
    assert response["error"] == "WrongCredentialsError: Invalid API key"
    
    # Verify vt.Client was called
    mock_vt_client.assert_called_once_with(API_KEY)


def test_get_ioc_report_no_api_key():
    """Test handling of missing API key"""
    action = GTIIoCReport()
    
    # Mock the configuration property to return an empty dict
    with patch.object(type(action.module), 'configuration', new_callable=PropertyMock) as mock_config:
        mock_config.return_value = {}
        
        response = action.run({"domain": DOMAIN})
        
        assert response is not None
        assert isinstance(response, dict)
        assert response.get("success") is False
        assert "API key" in response.get("error", "")


def test_get_ioc_report_no_parameters():
    """Test handling when no IoC parameters are provided"""
    action = GTIIoCReport()
    action.module.configuration = {"api_key": API_KEY}
    
    # Run with no parameters
    response = action.run({})
    
    # Verify error response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is False
    assert "must be provided" in response.get("error", "")


@patch('googlethreatintelligence.get_ioc_report.vt.Client')
@patch('googlethreatintelligence.get_ioc_report.VTAPIConnector')
def test_get_ioc_report_exception_handling(mock_connector_class, mock_vt_client):
    """Test general exception handling"""
    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance
    
    # Make VTAPIConnector raise an exception
    mock_connector_class.side_effect = Exception("Unexpected error occurred")
    
    # Setup action
    action = GTIIoCReport()
    action.module.configuration = {"api_key": API_KEY}
    
    # Run the action
    response = action.run({"domain": DOMAIN})
    
    # Verify error response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is False
    assert "Unexpected error occurred" in response.get("error", "")


@patch('googlethreatintelligence.get_ioc_report.vt.Client')
@patch('googlethreatintelligence.get_ioc_report.VTAPIConnector')
def test_get_ioc_report_multiple_parameters_domain_priority(mock_connector_class, mock_vt_client):
    """Test that domain takes priority when multiple parameters are provided"""
    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance
    
    # Mock VTAPIConnector instance
    mock_connector = MagicMock()
    mock_connector_class.return_value = mock_connector
    
    # Create a mock result
    mock_result = MagicMock()
    mock_result.status = "SUCCESS"
    mock_result.response = {"entity_type": "domains", "entity": DOMAIN}
    mock_result.error = None
    mock_connector.results = [mock_result]
    
    # Setup action
    action = GTIIoCReport()
    action.module.configuration = {"api_key": API_KEY}
    
    # Run with multiple parameters
    response = action.run({"domain": DOMAIN, "ip": IP, "url": URL})
    
    # Verify that domain report was called (domain has priority)
    mock_connector.get_domain_report.assert_called_once_with(mock_client_instance)
    mock_connector.get_ip_report.assert_not_called()
    mock_connector.get_url_report.assert_not_called()