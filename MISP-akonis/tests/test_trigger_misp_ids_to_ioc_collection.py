import pytest
from unittest.mock import Mock, patch, PropertyMock
from pymisp import PyMISPError
import requests

from misp.trigger_misp_ids_attributes_to_ioc_collection import MISPIDSAttributesToIOCCollectionTrigger


class TestMISPIDSAttributesToIOCCollectionTrigger:
    """Unit tests for MISP IDS Attributes to IOC Collection trigger."""

    # ------------------------------------------------------------------ #
    # Global test isolation (CRITICAL)
    # ------------------------------------------------------------------ #

    @pytest.fixture(autouse=True)
    def disable_trigger_logging(self, monkeypatch):
        """
        Disable Sekoia Trigger HTTP logging.
        Trigger.log() internally sends HTTP requests, which must never happen
        during unit tests.
        """
        monkeypatch.setattr(
            "sekoia_automation.trigger.Trigger._send_logs_to_api",
            lambda self: None,
        )

    @pytest.fixture
    def trigger(self):
        mock_module = Mock()
        mock_module.configuration = {
            "misp_url": "https://misp.example.com",
            "misp_api_key": "test_misp_api_key",
            "sekoia_api_key": "test_sekoia_api_key"
        }

        trigger = MISPIDSAttributesToIOCCollectionTrigger()
        trigger.module = mock_module
        trigger.configuration = {
            "ioc_collection_server": "https://api.sekoia.io",
            "ioc_collection_uuid": "test-collection-uuid",
            "publish_timestamp": "1",
            "sleep_time": "300",
        }

        trigger._logger = Mock()
        trigger.log = Mock()  # prevent Trigger.log() side effects
        return trigger

    # ------------------------------------------------------------------ #
    # Configuration properties
    # ------------------------------------------------------------------ #

    def test_sleep_time_default(self, trigger):
        trigger.configuration = {}
        assert trigger.sleep_time == 300

    def test_sleep_time_custom(self, trigger):
        trigger.configuration = {"sleep_time": "600"}
        assert trigger.sleep_time == 600

    def test_publish_timestamp_default(self, trigger):
        trigger.configuration = {}
        assert trigger.publish_timestamp == "1"

    def test_ioc_collection_server(self, trigger):
        assert trigger.ioc_collection_server == "https://api.sekoia.io"

    def test_ioc_collection_uuid(self, trigger):
        assert trigger.ioc_collection_uuid == "test-collection-uuid"

    #def test_sekoia_api_key(self, trigger):
    #    assert trigger.sekoia_api_key == "test_sekoia_api_key"

    # ------------------------------------------------------------------ #
    # Initialization
    # ------------------------------------------------------------------ #

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_success(self, mock_pymisp, trigger):
        misp = Mock()
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()

        assert trigger.misp_client == misp
        mock_pymisp.assert_called_once_with(
            url="https://misp.example.com",
            key="test_misp_api_key",
            ssl=False,
            debug=False,
        )

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_initialize_misp_client_error(self, mock_pymisp, trigger):
        mock_pymisp.side_effect = Exception("Connection failed")

        with pytest.raises(Exception, match="Connection failed"):
            trigger.initialize_misp_client()

    def test_initialize_cache_success(self, trigger):
        trigger.configuration["publish_timestamp"] = "7"
        trigger.initialize_cache()

        assert trigger.processed_attributes is not None
        assert trigger.processed_attributes.maxsize == 10000
        assert trigger.processed_attributes.ttl == 7 * 24 * 3600

    def test_initialize_cache_error(self, trigger):
        trigger.configuration["publish_timestamp"] = "invalid"

        with pytest.raises(Exception):
            trigger.initialize_cache()

    # ------------------------------------------------------------------ #
    # Filtering & extraction
    # ------------------------------------------------------------------ #

    def test_filter_supported_types(self, trigger):
        attrs = [
            Mock(type="ip-dst", value="1.1.1.1", uuid="1"),
            Mock(type="domain", value="example.com", uuid="2"),
            Mock(type="email-src", value="a@b.c", uuid="3"),
            Mock(type="sha256", value="a" * 64, uuid="4"),
            Mock(type="mutex", value="x", uuid="5"),
        ]

        filtered = trigger.filter_supported_types(attrs)

        assert [a.type for a in filtered] == ["ip-dst", "domain", "sha256"]

    def test_extract_ioc_value_simple(self, trigger):
        assert trigger.extract_ioc_value(Mock(type="ip-dst", value="1.1.1.1")) == "1.1.1.1"
        assert trigger.extract_ioc_value(Mock(type="domain", value="example.com")) == "example.com"
        assert trigger.extract_ioc_value(Mock(type="sha256", value="a" * 64)) == "a" * 64
        assert trigger.extract_ioc_value(Mock(type="url", value="https://evil")) == "https://evil"

    def test_extract_ioc_value_composite(self, trigger):
        sha256 = "a" * 64
        assert trigger.extract_ioc_value(Mock(type="filename|sha256", value=f"x.exe|{sha256}")) == sha256
        assert trigger.extract_ioc_value(Mock(type="filename|md5", value="x.exe|abc123")) == "abc123"
        assert trigger.extract_ioc_value(Mock(type="filename|sha1", value="x.exe|def456")) == "def456"
        assert trigger.extract_ioc_value(Mock(type="ip-dst|port", value="1.1.1.1|443")) == "1.1.1.1"
        assert trigger.extract_ioc_value(Mock(type="domain|ip", value="example.com|1.1.1.1")) == "example.com"

    def test_extract_ioc_value_unknown_type(self, trigger):
        attr = Mock(type="unknown-type", value="whatever")
        assert trigger.extract_ioc_value(attr) == "whatever"

    # ------------------------------------------------------------------ #
    # MISP
    # ------------------------------------------------------------------ #

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_fetch_attributes_success(self, mock_pymisp, trigger):
        misp = Mock()
        mock_pymisp.return_value = misp

        misp.search.return_value = [
            Mock(type="ip-dst", value="1.1.1.1", uuid="1"),
            Mock(type="domain", value="evil.com", uuid="2"),
        ]

        trigger.initialize_misp_client()
        attrs = trigger.fetch_attributes("1")

        assert len(attrs) == 2
        misp.search.assert_called_once_with(
            controller="attributes",
            to_ids=1,
            pythonify=True,
            publish_timestamp="1d",
        )

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_fetch_attributes_pymisp_error(self, mock_pymisp, trigger):
        misp = Mock()
        misp.search.side_effect = PyMISPError("boom")
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()

        with pytest.raises(PyMISPError):
            trigger.fetch_attributes("1")

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_fetch_attributes_generic_error(self, mock_pymisp, trigger):
        misp = Mock()
        misp.search.side_effect = Exception("Network error")
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()

        with pytest.raises(Exception, match="Network error"):
            trigger.fetch_attributes("1")

    # ------------------------------------------------------------------ #
    # Sekoia push
    # ------------------------------------------------------------------ #

    def test_push_to_sekoia_empty(self, trigger):
        """Test that empty list doesn't make any requests."""
        trigger.push_to_sekoia([])
        trigger.log.assert_called()

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    def test_push_to_sekoia_success(self, mock_post, trigger):
        resp = Mock(status_code=200)
        resp.json.return_value = {"created": 1, "updated": 0, "ignored": 0}
        mock_post.return_value = resp

        trigger.push_to_sekoia(["1.1.1.1", "evil.com"])

        payload = mock_post.call_args.kwargs["json"]
        assert payload["format"] == "one_per_line"
        assert "1.1.1.1" in payload["indicators"]

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_rate_limit_with_retry_after(self, mock_sleep, mock_post, trigger):
        r429 = Mock(status_code=429, headers={"Retry-After": "2"})
        r200 = Mock(status_code=200)
        r200.json.return_value = {"created": 1, "updated": 0, "ignored": 0}

        mock_post.side_effect = [r429, r200]

        trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(2)

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_rate_limit_without_retry_after(self, mock_sleep, mock_post, trigger):
        r429 = Mock(status_code=429, headers={})
        r200 = Mock(status_code=200)
        r200.json.return_value = {"created": 1, "updated": 0, "ignored": 0}

        mock_post.side_effect = [r429, r200]

        trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_post.call_count == 2
        # Should use exponential backoff: 2^0 * 10 = 10
        mock_sleep.assert_called_once_with(10)

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    def test_push_to_sekoia_auth_error_401(self, mock_post, trigger):
        resp = Mock(status_code=401, text="Unauthorized")
        mock_post.return_value = resp

        with pytest.raises(Exception, match="authentication error"):
            trigger.push_to_sekoia(["1.1.1.1"])

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    def test_push_to_sekoia_auth_error_403(self, mock_post, trigger):
        resp = Mock(status_code=403, text="Forbidden")
        mock_post.return_value = resp

        with pytest.raises(Exception, match="authentication error"):
            trigger.push_to_sekoia(["1.1.1.1"])

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    def test_push_to_sekoia_not_found_404(self, mock_post, trigger):
        resp = Mock(status_code=404, text="Not Found")
        mock_post.return_value = resp

        with pytest.raises(Exception, match="IOC Collection not found"):
            trigger.push_to_sekoia(["1.1.1.1"])

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_server_error_retry(self, mock_sleep, mock_post, trigger):
        r500 = Mock(status_code=500, text="Server Error")
        r200 = Mock(status_code=200)
        r200.json.return_value = {"created": 1, "updated": 0, "ignored": 0}

        mock_post.side_effect = [r500, r200]

        trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_post.call_count == 2
        mock_sleep.assert_called_with(5)

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_timeout(self, mock_sleep, mock_post, trigger):
        mock_post.side_effect = [
            requests.exceptions.Timeout("Timeout"),
            Mock(status_code=200, **{"json.return_value": {"created": 1, "updated": 0, "ignored": 0}}),
        ]

        trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_post.call_count == 2
        mock_sleep.assert_called_with(5)

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_request_exception(self, mock_sleep, mock_post, trigger):
        mock_post.side_effect = [
            requests.exceptions.RequestException("Connection error"),
            Mock(status_code=200, **{"json.return_value": {"created": 1, "updated": 0, "ignored": 0}}),
        ]

        trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_post.call_count == 2
        mock_sleep.assert_called_with(5)

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_max_retries_exceeded(self, mock_sleep, mock_post, trigger):
        resp = Mock(status_code=500, text="Server Error")
        mock_post.return_value = resp

        trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_post.call_count == 3  # max_retries
        trigger.log.assert_called()

    # ------------------------------------------------------------------ #
    # Run loop
    # ------------------------------------------------------------------ #

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_run_main_loop(self, mock_sleep, mock_pymisp, trigger):
        misp = Mock()
        misp.search.return_value = [
            Mock(type="ip-dst", value="1.1.1.1", uuid="1"),
            Mock(type="domain", value="evil.com", uuid="2"),
        ]
        mock_pymisp.return_value = misp

        with (
            patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post") as mock_post,
            patch.object(
                MISPIDSAttributesToIOCCollectionTrigger,
                "running",
                new_callable=PropertyMock,
            ) as running,
        ):
            running.side_effect = [True, False]

            resp = Mock(status_code=200)
            resp.json.return_value = {"created": 2, "updated": 0, "ignored": 0}
            mock_post.return_value = resp

            trigger.run()

        assert misp.search.called
        assert mock_post.called

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_run_no_new_iocs(self, mock_sleep, mock_pymisp, trigger):
        """Test when no new IOCs are found."""
        misp = Mock()
        misp.search.return_value = []
        mock_pymisp.return_value = misp

        with patch.object(
            MISPIDSAttributesToIOCCollectionTrigger,
            "running",
            new_callable=PropertyMock,
        ) as running:
            running.side_effect = [True, False]

            trigger.run()

        assert misp.search.called

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_run_with_error_recovery(self, mock_sleep, mock_pymisp, trigger):
        misp = Mock()
        misp.search.side_effect = [
            PyMISPError("temp"),
            [Mock(type="ip-dst", value="1.1.1.1", uuid="1")],
        ]
        mock_pymisp.return_value = misp

        with (
            patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post") as mock_post,
            patch.object(
                MISPIDSAttributesToIOCCollectionTrigger,
                "running",
                new_callable=PropertyMock,
            ) as running,
        ):
            running.side_effect = [True, True, False]

            resp = Mock(status_code=200)
            resp.json.return_value = {"created": 1, "updated": 0, "ignored": 0}
            mock_post.return_value = resp

            trigger.run()

        assert misp.search.call_count == 2
        assert 60 in [c.args[0] for c in mock_sleep.call_args_list]

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_run_keyboard_interrupt(self, mock_sleep, mock_pymisp, trigger):
        """Test graceful handling of KeyboardInterrupt."""
        misp = Mock()
        misp.search.side_effect = KeyboardInterrupt()
        mock_pymisp.return_value = misp

        with patch.object(
            MISPIDSAttributesToIOCCollectionTrigger,
            "running",
            new_callable=PropertyMock,
        ) as running:
            running.return_value = True

            trigger.run()

        trigger.log.assert_called()

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_run_initialization_failure(self, mock_pymisp, trigger):
        mock_pymisp.side_effect = Exception("init failed")
        trigger.run()
        trigger.log.assert_called()
