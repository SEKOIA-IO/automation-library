import requests_mock

from mandrill_module.action_mandrill_send import MandrillSendAction


def test_send_erroneous_email():
    action = MandrillSendAction()
    action.module.configuration = {"apikey": "my-fake-api-key"}

    with requests_mock.Mocker() as mock:
        send_result = {
            "status": "error",
            "code": 12,
            "name": "Unknown_Subaccount",
            "message": "No subaccount exists with the id 'customer-123'",
        }
        mock.post(
            "https://mandrillapp.com/api/1.0/messages/send.json",
            json=send_result,
            status_code=400,
            headers={"Content-Type": "application/json"},
        )

        message = {
            "html": "<p>Example email</p>",
            "text": "Example email",
            "from_email": "test-mandril-send@sekoia.io",
            "from_name": "Mandrill Send Action",
            "subject": "Test the Mandrill Send action",
            "to": [{"email": "recipient.email@example.com"}],
        }
        results = action.run({"message": message})
        assert results is None

        assert mock.call_count == 1
        query = mock.request_history[0]
        assert query.method == "POST"
        assert query.json()["message"] == message


def test_send_easy_email():
    action = MandrillSendAction()
    action.module.configuration = {"apikey": "my-fake-api-key"}

    with requests_mock.Mocker() as mock:
        send_result = [
            {
                "_id": "abc123abc123abc123abc123abc123",
                "email": "recipient.email@example.com",
                "reject_reason": "hard-bounce",
                "status": "sent",
            }
        ]
        mock.post(
            "https://mandrillapp.com/api/1.0/messages/send.json",
            json=send_result,
            headers={"Content-Type": "application/json"},
        )

        message = {
            "html": "<p>Example email</p>",
            "text": "Example email",
            "from_email": "test-mandril-send@sekoia.io",
            "from_name": "Mandrill Send Action",
            "subject": "Test the Mandrill Send action",
            "to": [{"email": "recipient.email@example.com"}],
        }
        results = action.run({"message": message})
        assert results == {"report": send_result}

        assert mock.call_count == 1
        query = mock.request_history[0]
        assert query.method == "POST"
        assert query.json()["message"] == message


def test_official_example():
    action = MandrillSendAction()
    action.module.configuration = {"apikey": "my-fake-api-key"}

    with requests_mock.Mocker() as mock:
        send_result = [
            {
                "_id": "abc123abc123abc123abc123abc123",
                "email": "recipient.email@example.com",
                "reject_reason": "hard-bounce",
                "status": "sent",
            }
        ]
        mock.post(
            "https://mandrillapp.com/api/1.0/messages/send.json",
            json=send_result,
            headers={"Content-Type": "application/json"},
        )

        message = {
            "attachments": [
                {
                    "content": "ZXhhbXBsZSBmaWxl",
                    "name": "myfile.txt",
                    "type": "text/plain",
                }
            ],
            "auto_html": None,
            "auto_text": None,
            "bcc_address": "message.bcc_address@example.com",
            "from_email": "message.from_email@example.com",
            "from_name": "Example Name",
            "global_merge_vars": [{"content": "merge1 content", "name": "merge1"}],
            "google_analytics_campaign": "message.from_email@example.com",
            "google_analytics_domains": ["example.com"],
            "headers": {"Reply-To": "message.reply@example.com"},
            "html": "<p>Example HTML content</p>",
            "images": [{"content": "ZXhhbXBsZSBmaWxl", "name": "IMAGECID", "type": "image/png"}],
            "important": False,
            "inline_css": None,
            "merge": True,
            "merge_language": "mailchimp",
            "merge_vars": [
                {
                    "rcpt": "recipient.email@example.com",
                    "vars": [{"content": "merge2 content", "name": "merge2"}],
                }
            ],
            "metadata": {"website": "www.example.com"},
            "preserve_recipients": None,
            "recipient_metadata": [{"rcpt": "recipient.email@example.com", "values": {"user_id": 123456}}],
            "return_path_domain": None,
            "signing_domain": None,
            "subaccount": "customer-123",
            "subject": "example subject",
            "tags": ["password-resets"],
            "text": {"plop": "Example text content"},
            "to": [
                {
                    "email": "recipient.email@example.com",
                    "name": "Recipient Name",
                    "type": "to",
                }
            ],
            "track_clicks": None,
            "track_opens": None,
            "tracking_domain": None,
            "url_strip_qs": None,
            "view_content_link": None,
        }
        results = action.run({"message": message})
        assert results == {"report": send_result}

        assert mock.call_count == 1
        query = mock.request_history[0]
        assert query.method == "POST"
        assert query.json()["message"] == message
        assert query.json()["ip_pool"] is None
        assert query.json()["send_at"] is None
