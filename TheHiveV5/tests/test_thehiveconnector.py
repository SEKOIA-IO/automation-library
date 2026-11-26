import os
import pytest
import sys
import unittest.mock as mock
import requests_mock

from thehive.thehiveconnector import (
    TheHiveConnector,
    key_exists,
    prepare_verify_param,
    _cleanup_ca_files,
)
from thehive4py.errors import TheHiveError


def test_key_exists_with_valid_string():
    """Test key_exists function with a valid string key"""
    mapping = {"key1": "value1", "key2": "value2"}
    assert key_exists(mapping, "key1") is True
    assert key_exists(mapping, "key3") is False


def test_key_exists_with_invalid_type():
    """Test that key_exists raises TypeError when key is not a string"""
    mapping = {"key1": "value1"}
    with pytest.raises(TypeError) as exc_info:
        key_exists(mapping, 123)
    assert "key_to_check must be a string" in str(exc_info.value)


def test_connector_init_without_apikey():
    """Test that ValueError is raised when API key is empty"""
    with pytest.raises(ValueError) as exc_info:
        TheHiveConnector("http://localhost:9000", "", "TESTORG")
    assert "API key is required" in str(exc_info.value)


class TestPrepareVerifyParam:
    """Tests for the prepare_verify_param helper function"""

    def test_verify_false_returns_false(self):
        """When verify is False, should return False regardless of ca_certificate"""
        assert prepare_verify_param(verify=False) is False
        assert prepare_verify_param(verify=False, ca_certificate="some cert") is False

    def test_verify_true_without_ca_returns_true(self):
        """When verify is True and no CA, should return True (use system CA store)"""
        assert prepare_verify_param(verify=True) is True
        assert prepare_verify_param(verify=True, ca_certificate=None) is True

    def test_verify_true_with_ca_returns_file_path(self):
        """When verify is True and CA provided, should return path to temp file"""
        ca_cert = "-----BEGIN CERTIFICATE-----\nTEST_UNIQUE_1\n-----END CERTIFICATE-----"
        result = prepare_verify_param(verify=True, ca_certificate=ca_cert)

        assert isinstance(result, str)
        assert result.endswith(".pem")
        assert os.path.exists(result)

        # Verify content
        with open(result, "r") as f:
            assert f.read() == ca_cert

    def test_same_ca_returns_cached_file(self):
        """Same CA certificate content should return the same cached file path"""
        ca_cert = "-----BEGIN CERTIFICATE-----\nTEST_CACHE\n-----END CERTIFICATE-----"
        result1 = prepare_verify_param(verify=True, ca_certificate=ca_cert)
        result2 = prepare_verify_param(verify=True, ca_certificate=ca_cert)

        assert result1 == result2
        assert os.path.exists(result1)

    def test_different_ca_returns_different_files(self):
        """Different CA certificates should return different file paths"""
        ca_cert1 = "-----BEGIN CERTIFICATE-----\nTEST_DIFF_1\n-----END CERTIFICATE-----"
        ca_cert2 = "-----BEGIN CERTIFICATE-----\nTEST_DIFF_2\n-----END CERTIFICATE-----"
        result1 = prepare_verify_param(verify=True, ca_certificate=ca_cert1)
        result2 = prepare_verify_param(verify=True, ca_certificate=ca_cert2)

        assert result1 != result2
        assert os.path.exists(result1)
        assert os.path.exists(result2)

    def test_cleanup_function_removes_files(self):
        """The cleanup function should remove all cached CA files"""
        ca_cert = "-----BEGIN CERTIFICATE-----\nTEST_CLEANUP\n-----END CERTIFICATE-----"
        result = prepare_verify_param(verify=True, ca_certificate=ca_cert)

        assert os.path.exists(result)

        # Call cleanup
        _cleanup_ca_files()

        # File should be removed
        assert not os.path.exists(result)


def test_connector_safe_call_with_thehive_error():
    """Test that _safe_call properly handles TheHiveError"""
    connector = TheHiveConnector("http://localhost:9000", "APIKEY123", "TESTORG")

    def mock_function():
        raise TheHiveError(message="Test error", response=None)

    with pytest.raises(TheHiveError):
        connector._safe_call(mock_function)


def test_connector_safe_call_with_generic_exception():
    """Test that _safe_call properly handles generic exceptions"""
    connector = TheHiveConnector("http://localhost:9000", "APIKEY123", "TESTORG")

    def mock_function():
        raise Exception("Generic error")

    with pytest.raises(Exception) as exc_info:
        connector._safe_call(mock_function)
    assert "Generic error" in str(exc_info.value)


def test_connector_alert_find():
    """Test alert_find method"""
    with requests_mock.Mocker() as mock_requests:
        url = "http://localhost:9000/api/v1/query"
        mock_requests.post(url=url, status_code=200, json=[{"_id": "alert1"}])

        connector = TheHiveConnector("http://localhost:9000", "APIKEY123", "TESTORG")
        result = connector.alert_find(filters={"status": "New"})

        # Verify the request was made
        assert mock_requests.call_count == 1


def test_sekoia_to_thehive_with_non_dict_event():
    """Test sekoia_to_thehive skips non-dict events"""
    # Test with a list containing non-dict items
    # sekoia_to_thehive is called as a class method where data becomes self
    data = [
        {"source.ip": "192.168.1.1"},
        "not a dict",  # This should be skipped
        123,  # This should also be skipped
        {"destination.domain": "example.com"},
    ]

    observables = TheHiveConnector.sekoia_to_thehive(data, "AMBER", "AMBER", True)

    # Should only have 2 observables (skipping the non-dict items)
    assert len(observables) == 2
    assert any(obs["data"] == "192.168.1.1" for obs in observables)
    assert any(obs["data"] == "example.com" for obs in observables)


def test_comment_add_in_alert():
    """Test comment_add_in_alert method"""
    with requests_mock.Mocker() as mock_requests:
        alert_id = "~12345"
        comment_text = "Test comment"
        url = f"http://localhost:9000/api/v1/alert/{alert_id}/comment"
        mock_requests.post(
            url=url,
            status_code=201,
            json={"_id": "comment123", "message": comment_text},
        )

        connector = TheHiveConnector("http://localhost:9000", "APIKEY123", "TESTORG")
        result = connector.comment_add_in_alert(alert_id, comment_text)

        # Verify the request was made
        assert mock_requests.call_count == 1


class TestPrepareVerifyParamEdgeCases:
    """Additional tests for prepare_verify_param edge cases"""

    def test_empty_certificate_returns_true(self):
        """Empty certificate string should return True (use system CA store)"""
        assert prepare_verify_param(verify=True, ca_certificate="") is True
        assert prepare_verify_param(verify=True, ca_certificate="   ") is True
        assert prepare_verify_param(verify=True, ca_certificate="\n\t") is True

    def test_line_ending_normalization(self):
        """Certificates with different line endings should use the same cache entry"""
        ca_cert_unix = "-----BEGIN CERTIFICATE-----\nTEST_LINE_ENDING\n-----END CERTIFICATE-----"
        ca_cert_windows = "-----BEGIN CERTIFICATE-----\r\nTEST_LINE_ENDING\r\n-----END CERTIFICATE-----"
        ca_cert_mac = "-----BEGIN CERTIFICATE-----\rTEST_LINE_ENDING\r-----END CERTIFICATE-----"

        result_unix = prepare_verify_param(verify=True, ca_certificate=ca_cert_unix)
        result_windows = prepare_verify_param(verify=True, ca_certificate=ca_cert_windows)
        result_mac = prepare_verify_param(verify=True, ca_certificate=ca_cert_mac)

        # All should return the same cached file
        assert result_unix == result_windows == result_mac

    def test_file_permissions(self):
        """CA certificate file should have restrictive permissions"""
        ca_cert = "-----BEGIN CERTIFICATE-----\nTEST_PERMISSIONS\n-----END CERTIFICATE-----"
        result = prepare_verify_param(verify=True, ca_certificate=ca_cert)

        # Check file permissions (0o600 = owner read/write only)
        file_stat = os.stat(result)
        permissions = file_stat.st_mode & 0o777
        assert permissions == 0o600

    def test_cache_recreates_deleted_file(self):
        """If cached file is deleted, a new one should be created"""
        ca_cert = "-----BEGIN CERTIFICATE-----\nTEST_RECREATE\n-----END CERTIFICATE-----"
        result1 = prepare_verify_param(verify=True, ca_certificate=ca_cert)

        # Delete the file
        os.unlink(result1)
        assert not os.path.exists(result1)

        # Call again - should create a new file
        result2 = prepare_verify_param(verify=True, ca_certificate=ca_cert)
        assert os.path.exists(result2)
        # New file path should be different since original was deleted
        assert result1 != result2

    def test_cleanup_clears_cache_dict(self):
        """Cleanup function should clear the cache dictionary"""
        import thehive.thehiveconnector as connector_module

        ca_cert = "-----BEGIN CERTIFICATE-----\nTEST_CACHE_CLEAR\n-----END CERTIFICATE-----"
        prepare_verify_param(verify=True, ca_certificate=ca_cert)

        # Cache should have entries
        assert len(connector_module._ca_file_cache) > 0

        # Call cleanup
        _cleanup_ca_files()

        # Cache should be empty
        assert len(connector_module._ca_file_cache) == 0

    def test_atexit_register_called_once(self):
        """atexit.register should only be called once"""
        import thehive.thehiveconnector as connector_module
        import atexit

        # Reset the flag for this test
        original_flag = connector_module._atexit_registered
        connector_module._atexit_registered = False

        with mock.patch.object(atexit, "register") as mock_register:
            ca_cert1 = "-----BEGIN CERTIFICATE-----\nTEST_ATEXIT_1\n-----END CERTIFICATE-----"
            ca_cert2 = "-----BEGIN CERTIFICATE-----\nTEST_ATEXIT_2\n-----END CERTIFICATE-----"

            prepare_verify_param(verify=True, ca_certificate=ca_cert1)
            prepare_verify_param(verify=True, ca_certificate=ca_cert2)

            # Should only be called once
            assert mock_register.call_count == 1
            mock_register.assert_called_once_with(connector_module._cleanup_ca_files)

        # Restore the flag
        connector_module._atexit_registered = True


def test_typed_inputs_fall_back_to_dict_without_thehive4py_types(monkeypatch):
    """When thehive4py typed inputs are unavailable, plain dicts are used instead"""
    import importlib.util
    import thehive.thehiveconnector as connector_module

    monkeypatch.setitem(sys.modules, "thehive4py.types.alert", None)
    spec = importlib.util.spec_from_file_location("thehive_connector_fallback", connector_module.__file__)
    fallback_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fallback_module)

    assert fallback_module.InputAlert is dict
    assert fallback_module.InputUpdateAlert is dict
    assert fallback_module.InputPromoteAlert is dict
    assert fallback_module.InputObservable is dict
    assert fallback_module.InputProcedure is dict


def test_cleanup_logs_and_clears_cache_when_unlink_fails(monkeypatch, caplog, tmp_path):
    """A CA file that cannot be removed is logged and the cache is still cleared"""
    import thehive.thehiveconnector as connector_module

    ca_file = tmp_path / "ca.pem"
    ca_file.write_text("cert")
    monkeypatch.setitem(connector_module._ca_file_cache, "cleanup-failure", str(ca_file))

    def failing_unlink(path):
        raise OSError("permission denied")

    monkeypatch.setattr(connector_module.os, "unlink", failing_unlink)

    with caplog.at_level("WARNING", logger="hive.alert.connector"):
        _cleanup_ca_files()

    assert "Failed to clean up temporary CA file" in caplog.text
    assert connector_module._ca_file_cache == {}
    assert ca_file.exists()


class TestPrepareVerifyParamWriteFailure:
    """prepare_verify_param must clean up the temp file and re-raise when writing fails"""

    @staticmethod
    def _record_mkstemp(monkeypatch, connector_module):
        created = []
        original_mkstemp = connector_module.tempfile.mkstemp

        def recording_mkstemp(*args, **kwargs):
            fd, path = original_mkstemp(*args, **kwargs)
            created.append(path)
            return fd, path

        monkeypatch.setattr(connector_module.tempfile, "mkstemp", recording_mkstemp)
        return created

    def test_chmod_failure_removes_temp_file(self, monkeypatch):
        import thehive.thehiveconnector as connector_module

        created = self._record_mkstemp(monkeypatch, connector_module)
        logs = []

        def failing_chmod(path, mode):
            raise PermissionError("chmod denied")

        monkeypatch.setattr(connector_module.os, "chmod", failing_chmod)

        ca_cert = "-----BEGIN CERTIFICATE-----\nTEST_CHMOD_FAILURE\n-----END CERTIFICATE-----"
        with pytest.raises(PermissionError):
            prepare_verify_param(verify=True, ca_certificate=ca_cert, log_fn=lambda msg, lvl: logs.append((msg, lvl)))

        assert len(created) == 1
        assert not os.path.exists(created[0])
        assert created[0] not in connector_module._ca_file_cache.values()
        assert any(lvl == "error" and "Failed to write CA cert" in msg for msg, lvl in logs)

    def test_write_failure_tolerates_close_and_unlink_errors(self, monkeypatch):
        import thehive.thehiveconnector as connector_module

        created = self._record_mkstemp(monkeypatch, connector_module)
        unlink_calls = []

        def failing_fsync(fd):
            raise OSError("disk full")

        def failing_unlink(path):
            unlink_calls.append(path)
            raise OSError("cannot remove")

        monkeypatch.setattr(connector_module.os, "fsync", failing_fsync)
        monkeypatch.setattr(connector_module.os, "unlink", failing_unlink)

        ca_cert = "-----BEGIN CERTIFICATE-----\nTEST_FSYNC_FAILURE\n-----END CERTIFICATE-----"
        with pytest.raises(OSError, match="disk full"):
            prepare_verify_param(verify=True, ca_certificate=ca_cert)

        monkeypatch.undo()
        assert unlink_calls == created
        assert created[0] not in connector_module._ca_file_cache.values()
        os.unlink(created[0])


def test_connector_init_logs_and_reraises_api_creation_error(monkeypatch):
    """A failure while building the TheHive client is logged as an error and re-raised"""
    import thehive.thehiveconnector as connector_module

    def failing_api(**kwargs):
        raise RuntimeError("bad url")

    monkeypatch.setattr(connector_module, "TheHiveApi", failing_api)
    logs = []

    with pytest.raises(RuntimeError, match="bad url"):
        TheHiveConnector("http://localhost:9000", "APIKEY123", "TESTORG", log_fn=lambda m, lvl: logs.append((m, lvl)))

    assert ("[TheHiveConnector.__init__] Failed to create TheHiveApi (RuntimeError): bad url", "error") in logs


class TestSekoiaToTheHiveLevels:
    """TLP/PAP conversion in sekoia_to_thehive"""

    def test_integer_levels_are_kept(self):
        observables = TheHiveConnector.sekoia_to_thehive([{"source.ip": "10.0.0.1"}], 4, 3, False)

        assert observables == [{"dataType": "ip", "data": "10.0.0.1", "tlp": 4, "pap": 3, "ioc": False}]

    def test_string_levels_are_case_insensitive(self):
        observables = TheHiveConnector.sekoia_to_thehive([{"source.ip": "10.0.0.1"}], "red", "green", True)

        assert observables[0]["tlp"] == 4
        assert observables[0]["pap"] == 1

    def test_unknown_levels_default_to_amber(self, caplog):
        with caplog.at_level("WARNING"):
            observables = TheHiveConnector.sekoia_to_thehive([{"source.ip": "10.0.0.1"}], "PURPLE", "BLUE", True)

        assert observables[0]["tlp"] == 2
        assert observables[0]["pap"] == 2
        assert "Unknown TLP level 'PURPLE'" in caplog.text
        assert "Unknown PAP level 'BLUE'" in caplog.text


def test_sekoia_to_thehive_converts_non_string_values():
    observables = TheHiveConnector.sekoia_to_thehive([{"user.name": 42}], "AMBER", "AMBER", True)

    assert observables == [{"dataType": "hostname", "data": "42", "tlp": 2, "pap": 2, "ioc": True}]


def test_sekoia_to_thehive_skips_fields_without_mapping(monkeypatch, caplog):
    import thehive.thehiveconnector as connector_module

    monkeypatch.setattr(connector_module, "SEKOIA_FIELDS", [*connector_module.SEKOIA_FIELDS, "custom.field"])

    with caplog.at_level("WARNING"):
        observables = TheHiveConnector.sekoia_to_thehive(
            [{"custom.field": "value", "source.ip": "10.0.0.1"}], "AMBER", "AMBER", True
        )

    assert observables == [{"dataType": "ip", "data": "10.0.0.1", "tlp": 2, "pap": 2, "ioc": True}]
    assert "unknown data type for field 'custom.field'" in caplog.text


def test_sekoia_to_thehive_deduplicates_observables():
    events = [{"source.ip": "10.0.0.1"}, {"source.ip": "10.0.0.1", "host.ip": "10.0.0.1"}]

    observables = TheHiveConnector.sekoia_to_thehive(events, "AMBER", "AMBER", True)

    assert observables == [{"dataType": "ip", "data": "10.0.0.1", "tlp": 2, "pap": 2, "ioc": True}]


def test_cleanup_skips_files_already_removed(monkeypatch, tmp_path):
    """Cached CA files that no longer exist are ignored by the cleanup"""
    import thehive.thehiveconnector as connector_module

    missing_file = tmp_path / "missing.pem"
    monkeypatch.setitem(connector_module._ca_file_cache, "already-removed", str(missing_file))

    _cleanup_ca_files()

    assert connector_module._ca_file_cache == {}
