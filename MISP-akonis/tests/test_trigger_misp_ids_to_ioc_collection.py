import pytest
from unittest.mock import Mock, patch, PropertyMock, call
from pymisp import PyMISPError

from misp.trigger_misp_ids_attributes_to_ioc_collection import MISPIDSAttributesToIOCCollectionTrigger


class TestMISPIDSAttributesToIOCCollectionTrigger:
    """Unit tests for MISP IDS Attributes to IOC Collection trigger."""

    @pytest.fixture
    def trigger(self):
        mock_module = Mock()
        mock_module.configuration = {
            "misp_url": "https://misp.example.com",
            "misp_api_key": "test_misp_api_key",
        }

        trigger = MISPIDSAttributesToIOCCollectionTrigger()
        trigger.module = mock_module
        trigger.configuration = {
            "ioc_collection_server": "https://api.sekoia.io",
            "ioc_collection_uuid": "test-collection-uuid",
            "sekoia_api_key": "test_sekoia_api_key",
            "publish_timestamp": "1",
            "sleep_time": "300",
        }
        trigger._logger = Mock()
        return trigger

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
        assert trigger.extract_ioc_value(Mock(type="ip-dst|port", value="1.1.1.1|443")) == "1.1.1.1"
        assert trigger.extract_ioc_value(Mock(type="domain|ip", value="example.com|1.1.1.1")) == "example.com"

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
    def test_fetch_attributes_error(self, mock_pymisp, trigger):
        misp = Mock()
        misp.search.side_effect = PyMISPError("boom")
        mock_pymisp.return_value = misp

        trigger.initialize_misp_client()

        with pytest.raises(PyMISPError):
            trigger.fetch_attributes("1")

    # ------------------------------------------------------------------ #
    # Sekoia push
    # ------------------------------------------------------------------ #

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    def test_push_to_sekoia_success(self, mock_post, trigger):
        resp = Mock(status_code=200)
        resp.json.return_value = {"created": 1, "updated": 0, "ignored": 0}
        mock_post.return_value = resp

        trigger.push_to_sekoia(["1.1.1.1", "evil.com"])

        assert mock_post.call_count == 1
        payload = mock_post.call_args.kwargs["json"]
        assert payload["format"] == "one_per_line"
        assert "1.1.1.1" in payload["indicators"]

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.requests.post")
    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.time.sleep")
    def test_push_to_sekoia_rate_limit(self, mock_sleep, mock_post, trigger):
        r429 = Mock(status_code=429, headers={"Retry-After": "2"})
        r200 = Mock(status_code=200)
        r200.json.return_value = {"created": 1, "updated": 0, "ignored": 0}

        mock_post.side_effect = [r429, r200]

        trigger.push_to_sekoia(["1.1.1.1"])

        assert mock_post.call_count == 2
        mock_sleep.assert_called_once_with(2)

    # ------------------------------------------------------------------ #
    # Run loop (FIXED)
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
    def test_run_initialization_failure(self, mock_pymisp, trigger):
        mock_pymisp.side_effect = Exception("init failed")

        trigger.run()

        trigger._logger.error.assert_called()

    @patch("misp.trigger_misp_ids_attributes_to_ioc_collection.PyMISP")
    def test_run_keyboard_interrupt(self, mock_pymisp, trigger):
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

        msgs = [c.args[0].lower() for c in trigger._logger.info.call_args_list]
        assert any("stopped" in m for m in msgs)
