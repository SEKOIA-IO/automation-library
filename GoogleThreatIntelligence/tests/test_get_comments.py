import os
import pytest
from unittest.mock import MagicMock, patch
import vt
from googlethreatintelligence.get_comments import GTIGetComments

HOST = "https://www.virustotal.com"
DOMAIN = "google.com"
API_KEY = os.getenv("VT_API_KEY", "FAKE_API_KEY")


@pytest.fixture
def action():
    act = GTIGetComments()
    act.module.configuration = {"api_key": API_KEY}
    return act


def test_get_comments_success_offline(action):
    fake_comment = MagicMock()
    fake_comment.text = "Mocked comment"
    fake_comment.date = "2024-01-01"
    fake_comment.votes = {"positive": 1, "negative": 0}
    fake_comment.author = "tester"

    fake_client = MagicMock()
    fake_client.iterator.return_value = [fake_comment]

    with patch("googlethreatintelligence.get_comments.vt.Client", return_value=fake_client):
        response = action.run({"entity_type": "domains", "entity": DOMAIN})

    assert isinstance(response, dict)
    assert response["success"] is True
    assert "data" in response
    assert "comments" in response["data"]

    comments = response["data"]["comments"]
    if comments:
        assert comments[0]["text"] == "Mocked comment"


def test_get_comments_fail_offline(action):
    fake_client = MagicMock()
    fake_client.iterator.side_effect = vt.error.APIError("InvalidArgumentError", "Invalid API key")

    with patch("googlethreatintelligence.get_comments.vt.Client", return_value=fake_client):
        response = action.run({"entity_type": "domains", "entity": DOMAIN})

    assert isinstance(response, dict)
    assert response["success"] is False
    assert "Invalid API key" in response["error"]


def test_get_comments_no_api_key():
    action = GTIGetComments()
    action.module.configuration = {"api_key": None}
    response = action.run({"entity_type": "domains", "entity": DOMAIN})
    assert response["success"] is False
    assert "API key" in response["error"]


@pytest.mark.skipif(
    os.getenv("VT_API_KEY") is None,
    reason="Integration test requires real VirusTotal API key (VT_API_KEY)",
)
def test_get_comments_integration(action):
    response = action.run({"entity_type": "domains", "entity": DOMAIN})
    assert isinstance(response, dict)
    assert "success" in response
