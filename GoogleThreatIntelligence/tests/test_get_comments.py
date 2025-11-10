import json
import urllib.parse
import requests_mock
from googlethreatintelligence.get_comments import GTIGetComments

HOST = "https://threatintelligence.googleapis.com/"
API_KEY = "FAKE_API_KEY"
DOMAIN = "google.com"

GTI_OUTPUT =   {
    "name": "GET_COMMENTS",
    "method": "GET",
    "url": "/api/v3/domains/google.com/comments",
    "status": 200,
    "response": {
      "data": [
        {
          "id": "d-google.com-7fa0af5c",
          "type": "comment",
          "links": {
            "self": "https://www.virustotal.com/api/v3/comments/d-google.com-7fa0af5c"
          },
          "attributes": {
            "date": 1757084231,
            "tags": [],
            "votes": {
              "positive": 0,
              "negative": 0,
              "abuse": 0
            },
            "text": "Test comment",
            "html": "Test comment"
          }
        },
        {
          "id": "d-google.com-79574dd4",
          "type": "comment",
          "links": {
            "self": "https://www.virustotal.com/api/v3/comments/d-google.com-79574dd4"
          },
          "attributes": {
            "date": 1756785681,
            "tags": [],
            "votes": {
              "positive": 0,
              "negative": 0,
              "abuse": 0
            },
            "text": "This site impersonates the official Bibit website, disseminating false customer service numbers to deceive customers. Fraudulent agents then solicit personal data, passwords, and OTPs, leading to account takeovers and financial losses. Authentic Bibit customer support is exclusively available at https://bibit.id/. We request the immediate takedown of this fraudulent site to prevent further harm.",
            "html": "This site impersonates the official Bibit website, disseminating false customer service numbers to deceive customers. Fraudulent agents then solicit personal data, passwords, and OTPs, leading to account takeovers and financial losses. Authentic Bibit customer support is exclusively available at https://bibit.id/. We request the immediate takedown of this fraudulent site to prevent further harm."
          }
        },
        {
          "id": "d-google.com-dab4ca28",
          "type": "comment",
          "links": {
            "self": "https://www.virustotal.com/api/v3/comments/d-google.com-dab4ca28"
          },
          "attributes": {
            "date": 1756160380,
            "tags": [],
            "votes": {
              "positive": 0,
              "negative": 0,
              "abuse": 0
            },
            "text": "Search engine.",
            "html": "Search engine."
          }
        },
        {
          "id": "d-google.com-70a69f8a",
          "type": "comment",
          "links": {
            "self": "https://www.virustotal.com/api/v3/comments/d-google.com-70a69f8a"
          },
          "attributes": {
            "date": 1751846384,
            "tags": [],
            "votes": {
              "positive": 0,
              "negative": 0,
              "abuse": 0
            },
            "text": "🔍 Collection: LIVE VT Upload Demo | 📝 Description: 🎯 LIVE VT UPLOAD TEST via caz-vt-feeder - Domain Comment Added | 🏷️ Tags: live-upload-test, caz-vt-feeder | 📡 Source: caz-vt-feeder-system",
            "html": "🔍 Collection: LIVE VT Upload Demo | 📝 Description: 🎯 LIVE VT UPLOAD TEST via caz-vt-feeder - Domain Comment Added | 🏷️ Tags: live-upload-test, caz-vt-feeder | 📡 Source: caz-vt-feeder-system"
          }
        },
        {
          "id": "d-google.com-105298ff",
          "type": "comment",
          "links": {
            "self": "https://www.virustotal.com/api/v3/comments/d-google.com-105298ff"
          },
          "attributes": {
            "date": 1751846033,
            "tags": [],
            "votes": {
              "positive": 0,
              "negative": 0,
              "abuse": 0
            },
            "text": "🔍 Collection: Live Test Upload | 📝 Description: Test domain for VT comment upload | 🏷️ Tags: test, domain | 📡 Source: caz-vt-feeder-live-test",
            "html": "🔍 Collection: Live Test Upload | 📝 Description: Test domain for VT comment upload | 🏷️ Tags: test, domain | 📡 Source: caz-vt-feeder-live-test"
          }
        },
        {
          "id": "d-google.com-7c862874",
          "type": "comment",
          "links": {
            "self": "https://www.virustotal.com/api/v3/comments/d-google.com-7c862874"
          },
          "attributes": {
            "date": 1751845799,
            "tags": [],
            "votes": {
              "positive": 0,
              "negative": 0,
              "abuse": 0
            },
            "text": "🔍 Collection: Test Official Upload | 📝 Description: Test domain upload | 🏷️ Tags: test, domain | 📡 Source: caz-vt-feeder-test",
            "html": "🔍 Collection: Test Official Upload | 📝 Description: Test domain upload | 🏷️ Tags: test, domain | 📡 Source: caz-vt-feeder-test"
          }
        },
        {
          "id": "d-google.com-475e081f",
          "type": "comment",
          "links": {
            "self": "https://www.virustotal.com/api/v3/comments/d-google.com-475e081f"
          },
          "attributes": {
            "date": 1749772386,
            "tags": [],
            "votes": {
              "positive": 0,
              "negative": 0,
              "abuse": 0
            },
            "text": "VIRUSSSSSSSVIRUSSSS GOOGLE BAD",
            "html": "VIRUSSSSSSSVIRUSSSS GOOGLE BAD"
          }
        },
        {
          "id": "d-google.com-9f8fab3d",
          "type": "comment",
          "links": {
            "self": "https://www.virustotal.com/api/v3/comments/d-google.com-9f8fab3d"
          },
          "attributes": {
            "date": 1749586280,
            "tags": [],
            "votes": {
              "positive": 0,
              "negative": 0,
              "abuse": 0
            },
            "text": "it's google!!!",
            "html": "it&#39;s google!!!"
          }
        },
        {
          "id": "d-google.com-6beac8d5",
          "type": "comment",
          "links": {
            "self": "https://www.virustotal.com/api/v3/comments/d-google.com-6beac8d5"
          },
          "attributes": {
            "date": 1749535654,
            "tags": [],
            "votes": {
              "positive": 0,
              "negative": 0,
              "abuse": 0
            },
            "text": "Lorem ipsum dolor sit ...",
            "html": "Lorem ipsum dolor sit &#8230;"
          }
        },
        {
          "id": "d-google.com-09720039",
          "type": "comment",
          "links": {
            "self": "https://www.virustotal.com/api/v3/comments/d-google.com-09720039"
          },
          "attributes": {
            "date": 1749535642,
            "tags": [],
            "votes": {
              "positive": 0,
              "negative": 0,
              "abuse": 0
            },
            "text": "Lorem ipsum dolor sit ...",
            "html": "Lorem ipsum dolor sit &#8230;"
          }
        }
      ],
      "meta": {
        "count": 200,
        "cursor": "CmQKEQoEZGF0ZRIJCJSMkZSY5o0DEktqEXN-dmlydXN0b3RhbGNsb3VkcjYLEgZEb21haW4iCmdvb2dsZS5jb20MCxIHQ29tbWVudCITZ29vZ2xlLmNvbS0wOTcyMDAzOQwYACAB"
      },
      "links": {
        "self": "https://www.virustotal.com/api/v3/domains/google.com/comments?limit=10",
        "next": "https://www.virustotal.com/api/v3/domains/google.com/comments?limit=10&cursor=CmQKEQoEZGF0ZRIJCJSMkZSY5o0DEktqEXN-dmlydXN0b3RhbGNsb3VkcjYLEgZEb21haW4iCmdvb2dsZS5jb20MCxIHQ29tbWVudCITZ29vZ2xlLmNvbS0wOTcyMDAzOQwYACAB"
      }
    }
  }

def _qs_matcher(expected_params):
    def matcher(request):
        actual = {k: v[0] if isinstance(v, list) else v for k, v in request.qs.items()}
        for key, value in expected_params.items():
            if key not in actual or actual[key] != str(value):
                return False
        return True
    return matcher


def test_get_comments_success():
    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = f"/v1/domains/{DOMAIN}/comments"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            json=GTI_OUTPUT,
            status_code=200,
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"entity_type": "domains"})
        assert response is not None
        data = json.loads(response) if isinstance(response, str) else response
        assert "comments" in data or (data.get("data") and "comments" in data.get("data"))
        assert mock_requests.call_count == 1


def test_get_comments_not_found():
    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = f"/v1/domains/{DOMAIN}/comments"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            status_code=404,
            json={"error": {"message": "Not Found"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"entity_type": "domains"})
        assert response is not None
        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or data.get("success") is False
        assert mock_requests.call_count == 1


def test_get_comments_api_error():
    action = GTIGetComments()
    action.module.configuration = {"api_key": API_KEY, "host": HOST.rstrip("/")}

    uri = f"/v1/domains/{DOMAIN}/comments"

    with requests_mock.Mocker() as mock_requests:
        mock_requests.get(
            urllib.parse.urljoin(HOST, uri),
            status_code=500,
            json={"error": {"message": "Internal Server Error"}},
            additional_matcher=_qs_matcher({"key": API_KEY})
        )

        response = action.run({"entity_type": "domains"})
        assert response is not None
        data = json.loads(response) if isinstance(response, str) else response
        assert "error" in data or data.get("success") is False
        assert mock_requests.call_count == 1
