import json
import urllib.parse
import requests_mock
from googlethreatintelligence.get_comments import GTIGetComments

# === Test constants ===
HOST = "https://www.virustotal.com"
API_KEY = "FAKE_API_KEY"
DOMAIN = "google.com"

# Mock response matching VT API structure
VT_API_RESPONSE = {
    "data": [
        {
            "type": "comment",
            "id": "d-google.com-1234",
            "attributes": {
                "text": "Test comment",
                "date": 1630857431,
                "votes": {
                    "positive": 0,
                    "negative": 0
                }
            }
        }
    ]
}

def test_get_comments_success():
    """Test successful retrieval of comments"""
    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY}

    # The actual endpoint that vt.Client will call
    endpoint = f"{HOST}/api/v3/domains/{DOMAIN}/comments"

    with requests_mock.Mocker() as mock_requests:
        # Mock the VT API endpoint
        mock_requests.get(
            endpoint,
            json=VT_API_RESPONSE,
            status_code=200
        )

        # Run the action with proper parameters
        response = action.run({
            "entity_type": "domains",
            "entity": DOMAIN
        })
        
        # Verify response
        assert response is not None
        assert isinstance(response, dict)
        assert response.get("success") is True
        assert "data" in response
        
        # Verify the mock was called
        assert mock_requests.call_count == 1
        
        # Verify the request was made to the correct URL
        assert mock_requests.request_history[0].url == endpoint


def test_get_comments_fail():
    """Test error handling when API fails"""
    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY}

    endpoint = f"{HOST}/api/v3/domains/{DOMAIN}/comments"

    with requests_mock.Mocker() as mock_requests:
        # Mock an API error response
        mock_requests.get(
            endpoint,
            json={"error": {"message": "Invalid API key"}},
            status_code=401
        )

        # Run the action
        response = action.run({
            "entity_type": "domains",
            "entity": DOMAIN
        })
        
        # Verify error response
        assert response is not None
        assert isinstance(response, dict)
        
        # The response should indicate failure
        assert response.get("success") is False or "error" in response
        
        # Verify the mock was called
        assert mock_requests.call_count == 1


def test_get_comments_no_api_key():
    """Test handling of missing API key"""
    action = GTIGetComments()
    action.module.configuration = {}

    response = action.run({
        "entity_type": "domains",
        "entity": DOMAIN
    })
    
    assert response is not None
    assert isinstance(response, dict)
    assert response.get("success") is False
    assert "API key" in response.get("error", "")