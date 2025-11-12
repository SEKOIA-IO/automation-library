from unittest.mock import patch, MagicMock, PropertyMock
import vt
from googlethreatintelligence.get_comments import GTIGetComments

# === Test constants ===
API_KEY = "FAKE_API_KEY"
DOMAIN = "google.com"

@patch('googlethreatintelligence.get_comments.vt.Client')
def test_get_comments_success(mock_vt_client):
    """Test successful retrieval of comments"""
    # Create a mock comment object with the attributes expected by VTAPIConnector
    mock_comment = MagicMock()
    mock_comment.text = "Test comment"
    mock_comment.date = "2021-09-05 10:30:31"
    mock_comment.votes = {"positive": 5, "negative": 1}
    mock_comment.author = "test_user"

    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Mock the iterator to return our fake comment
    mock_client_instance.iterator.return_value = iter([mock_comment])

    # Setup action
    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY}

    # Run the action
    response = action.run({
        "entity_type": "domains",
        "entity": DOMAIN
    })

    # Verify response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is True
    assert "data" in response

    # Verify the data contains comment information
    assert response["data"]["comments_count"] == 1
    assert response["data"]["entity"] == DOMAIN
    assert len(response["data"]["comments"]) == 1
    assert response["data"]["comments"][0]["text"] == "Test comment"

    # Verify vt.Client was called with the correct API key
    mock_vt_client.assert_called_once_with(API_KEY)

    # Verify iterator was called with the correct endpoint
    mock_client_instance.iterator.assert_called_once_with(
        f"/domains/{DOMAIN}/comments",
        limit=10
    )


@patch('googlethreatintelligence.get_comments.vt.Client')
def test_get_comments_fail(mock_vt_client):
    """Test error handling when API fails"""
    # Mock the vt.Client context manager
    mock_client_instance = MagicMock()
    mock_vt_client.return_value.__enter__.return_value = mock_client_instance

    # Simulate an API error when calling iterator
    # vt.APIError requires two arguments: error_code and message
    mock_client_instance.iterator.side_effect = vt.APIError("WrongCredentialsError", "Invalid API key")

    # Setup action
    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY}

    # Run the action
    response = action.run({
        "entity_type": "domains",
        "entity": DOMAIN
    })

    # Verify error response
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is False
    assert "data" in response

    # Verify vt.Client was called
    mock_vt_client.assert_called_once_with(API_KEY)


def test_get_comments_no_api_key():
    """Test handling of missing API key"""
    action = GTIGetComments()

    # Mock the configuration property to return an empty dict
    with patch.object(type(action.module), 'configuration', new_callable=PropertyMock) as mock_config:
        mock_config.return_value = {}

        response = action.run({
            "entity_type": "domains",
            "entity": DOMAIN
        })

        assert response is not None
        assert isinstance(response, dict)
        assert response.get("success") is False
        assert "API key" in response.get("error", "")