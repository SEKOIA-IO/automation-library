from unittest.mock import Mock, patch

import pytest
import urllib3

from imperva.fetch_logs import FileDownloader, HTTPError


def test_file_downloader_200_with_proxy(config):
    config.USE_PROXY = "YES"
    config.USE_CUSTOM_CA_FILE = "YES"
    config.PROXY_SERVER = "https://pro.xy"

    fd = FileDownloader(config, Mock)

    with patch("urllib3.ProxyManager") as m:
        mock_http = m.return_value
        mock_http.request.return_value = Mock(status=200, data=b"some data")

        result = fd.request_file_content(config.BASE_URL, timeout=1)
        assert result == b"some data"

        mock_http.request.assert_called_once_with(
            "GET", config.BASE_URL, headers={"authorization": "Basic bG9yZW06aXBzdW0="}
        )


def test_file_downloader_404(config):
    fd = FileDownloader(config, Mock)

    with patch("urllib3.PoolManager") as m:
        mock_http = m.return_value
        mock_http.request.return_value = Mock(status=404, data=b"not found")

        result = fd.request_file_content(config.BASE_URL, timeout=1)

        assert result == b""

        mock_http.request.assert_called_once_with(
            "GET", config.BASE_URL, headers={"authorization": "Basic bG9yZW06aXBzdW0="}
        )


def test_file_downloader_401(config):
    fd = FileDownloader(config, Mock)

    with patch("urllib3.PoolManager") as m:
        mock_http = m.return_value
        mock_http.request.return_value = Mock(status=401)

        with pytest.raises(HTTPError):
            fd.request_file_content(config.BASE_URL, timeout=1)

        mock_http.request.assert_called_once_with(
            "GET", config.BASE_URL, headers={"authorization": "Basic bG9yZW06aXBzdW0="}
        )


def test_file_downloader_429(config):
    fd = FileDownloader(config, Mock)

    with patch("urllib3.PoolManager") as m:
        mock_http = m.return_value
        mock_http.request.return_value = Mock(status=429)

        with pytest.raises(HTTPError):
            fd.request_file_content(config.BASE_URL, timeout=1)

        mock_http.request.assert_called_once_with(
            "GET", config.BASE_URL, headers={"authorization": "Basic bG9yZW06aXBzdW0="}
        )


def test_file_downloader_other(config):
    fd = FileDownloader(config, Mock)

    with patch("urllib3.PoolManager") as m:
        mock_http = m.return_value
        mock_http.request.return_value = Mock(status=500)

        result = fd.request_file_content(config.BASE_URL, timeout=1)
        assert result == b""

        mock_http.request.assert_called_once_with(
            "GET", config.BASE_URL, headers={"authorization": "Basic bG9yZW06aXBzdW0="}
        )


def test_file_downloader_urllib_exception(config):
    fd = FileDownloader(config, Mock)

    with patch("urllib3.PoolManager") as m:
        mock_http = m.return_value
        mock_http.request.side_effect = urllib3.exceptions.HTTPError

        with pytest.raises(HTTPError):
            fd.request_file_content(config.BASE_URL, timeout=1)

        mock_http.request.assert_called_once_with(
            "GET", config.BASE_URL, headers={"authorization": "Basic bG9yZW06aXBzdW0="}
        )
