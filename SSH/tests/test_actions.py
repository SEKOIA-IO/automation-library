import socket
import time
from unittest.mock import MagicMock

import paramiko
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import dsa, rsa

from ssh_remote import SSHModule
from ssh_remote.actions import RunSSHCommand, RunSSHScript
from ssh_remote.client import SSHExecutionError, load_private_key, parse_fingerprints
from ssh_remote.models import SSHModuleConfiguration


def _action(cls, data_storage, **config):
    module = SSHModule()
    module.configuration = SSHModuleConfiguration(username="tester", **config)
    action = cls(module=module, data_path=data_storage)
    action.send_results = MagicMock()
    return action


def _config(server, **overrides):
    config = {
        "host": server["host"],
        "port": server["port"],
        "private_key": server["private_key"],
        "host_key_fingerprint": server["host_key_fingerprint"],
    }
    config.update(overrides)
    return config


def test_run_command(ssh_server, data_storage):
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server))
    result = action.run({"command": "echo hello; echo oops >&2"})

    assert action.error_message is None
    assert result["exit_code"] == 0
    assert result["stdout"] == "hello\n"
    assert result["stderr"] == "oops\n"
    assert result["host"] == "127.0.0.1"
    assert result["host_key_fingerprint"] == ssh_server["host_key_fingerprint"]


def test_run_command_nonzero_exit_fails(ssh_server, data_storage):
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server))
    result = action.run({"command": "echo boom >&2; exit 3"})

    assert result["exit_code"] == 3
    assert "exited with code 3" in action.error_message
    assert "boom" in action.error_message


def test_run_command_nonzero_exit_tolerated(ssh_server, data_storage):
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server))
    result = action.run({"command": "exit 2", "fail_on_error": False})

    assert result["exit_code"] == 2
    assert action.error_message is None


def test_run_script(ssh_server, data_storage):
    action = _action(RunSSHScript, data_storage, **_config(ssh_server))
    script = 'X=41\r\nY=$((X+1))\r\necho "answer=$Y"'
    result = action.run({"script": script, "interpreter": "/bin/sh -s"})

    assert action.error_message is None
    assert result["stdout"] == "answer=42\n"


def test_password_auth(ssh_server, data_storage):
    action = _action(
        RunSSHCommand,
        data_storage,
        **_config(ssh_server, private_key=None, password=ssh_server["password"]),
    )
    result = action.run({"command": "echo ok"})

    assert result["stdout"] == "ok\n"


def test_pinned_fingerprint_ok(ssh_server, data_storage):
    action = _action(
        RunSSHCommand,
        data_storage,
        **_config(ssh_server, host_key_fingerprint=ssh_server["host_key_fingerprint"]),
    )
    assert action.run({"command": "true"})["exit_code"] == 0


def test_pinned_fingerprint_mismatch(ssh_server, data_storage):
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server, host_key_fingerprint="SHA256:notthekey"))
    assert action.run({"command": "true"}) is None
    assert "Host key mismatch" in action.error_message
    assert ssh_server["host_key_fingerprint"] in action.error_message


def test_key_with_escaped_newlines(ssh_server, data_storage):
    escaped = ssh_server["private_key"].replace("\n", "\\n")
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server, private_key=escaped))
    assert action.run({"command": "echo ok"})["stdout"] == "ok\n"


def test_wrong_key_rejected(ssh_server, data_storage):
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()
    )
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server, private_key=other.decode()))
    assert action.run({"command": "true"}) is None
    assert "Authentication failed" in action.error_message


def test_timeout(ssh_server, data_storage):
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server))
    assert action.run({"command": "sleep 5", "timeout": 1}) is None
    assert "timed out" in action.error_message


def test_host_override_unreachable(ssh_server, data_storage):
    config = _config(ssh_server, connect_timeout=2, allowed_hosts=["127.0.0.2"])
    action = _action(RunSSHCommand, data_storage, **config)
    assert action.run({"command": "true", "host": "127.0.0.2"}) is None
    assert "Unable to connect to 127.0.0.2" in action.error_message


def test_no_credentials(data_storage):
    action = _action(RunSSHCommand, data_storage, host="127.0.0.1")
    assert action.run({"command": "true"}) is None
    assert "private key or a password" in action.error_message


def test_empty_inputs(data_storage):
    cmd = _action(RunSSHCommand, data_storage, host="127.0.0.1", password="x")
    assert cmd.run({"command": "  "}) is None
    assert cmd.error_message == "The command is empty"

    script = _action(RunSSHScript, data_storage, host="127.0.0.1", password="x")
    assert script.run({"script": ""}) is None
    assert script.error_message == "The script is empty"


def test_encrypted_key_needs_passphrase():
    pem = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.BestAvailableEncryption(b"pass"),
        )
        .decode()
    )

    with pytest.raises(SSHExecutionError, match="passphrase"):
        load_private_key(pem, None)
    assert isinstance(load_private_key(pem, "pass"), paramiko.RSAKey)


def test_invalid_key():
    with pytest.raises(SSHExecutionError, match="Unable to load the private key"):
        load_private_key("not a key", None)


def test_unpinned_host_key_refused_by_default(ssh_server, data_storage):
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server, host_key_fingerprint=None))
    assert action.run({"command": "true"}) is None
    assert "is not pinned" in action.error_message
    # The error gives the fingerprint to pin
    assert ssh_server["host_key_fingerprint"] in action.error_message


def test_unpinned_host_key_accepted_on_opt_in(ssh_server, data_storage):
    action = _action(
        RunSSHCommand, data_storage, **_config(ssh_server, host_key_fingerprint="", accept_unknown_host_keys=True)
    )
    result = action.run({"command": "echo ok"})
    assert result["stdout"] == "ok\n"
    assert result["host_key_fingerprint"] == ssh_server["host_key_fingerprint"]


def test_several_pinned_fingerprints(ssh_server, data_storage):
    # Prefix-less and "="-padded forms are accepted too
    pinned = "SHA256:other, " + ssh_server["host_key_fingerprint"].removeprefix("SHA256:") + "="
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server, host_key_fingerprint=pinned))
    assert action.run({"command": "true"})["exit_code"] == 0


def test_parse_fingerprints():
    assert parse_fingerprints("SHA256:a=, sha256:b\nc") == {"SHA256:a", "SHA256:b", "SHA256:c"}
    assert parse_fingerprints(None) == set()


def test_host_override_refused_when_not_allowed(ssh_server, data_storage):
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server))
    assert action.run({"command": "true", "host": "10.0.0.1"}) is None
    assert "10.0.0.1 is not allowed" in action.error_message


def test_host_override_allowed(ssh_server, data_storage):
    # The account host is unreachable; the allowed override points at the test server
    action = _action(
        RunSSHCommand, data_storage, **_config(ssh_server, host="127.0.0.2", allowed_hosts=[ssh_server["host"]])
    )
    result = action.run({"command": "echo ok", "host": ssh_server["host"]})
    assert result["stdout"] == "ok\n"
    assert result["host"] == ssh_server["host"]


def test_host_override_same_as_account_host(ssh_server, data_storage):
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server))
    assert action.run({"command": "true", "host": ssh_server["host"]})["exit_code"] == 0


def test_command_reading_stdin_gets_eof(ssh_server, data_storage):
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server))
    result = action.run({"command": "cat; echo done", "timeout": 5})
    assert action.error_message is None
    assert result["stdout"] == "done\n"


def test_timeout_during_session_setup(ssh_server, data_storage):
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server))
    started = time.monotonic()
    assert action.run({"command": "__hang__", "timeout": 1}) is None
    assert "timed out after 1s" in action.error_message
    assert time.monotonic() - started < 4


def test_session_setup_error_is_reported(ssh_server, data_storage, monkeypatch):
    def refuse(*args, **kwargs):
        raise paramiko.ChannelException(1, "Administratively prohibited")

    monkeypatch.setattr(paramiko.Transport, "open_session", refuse)
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server))
    assert action.run({"command": "true"}) is None
    assert "SSH session with 127.0.0.1 failed" in action.error_message


def test_dns_timeout(data_storage, monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", lambda *args, **kwargs: time.sleep(5))
    action = _action(RunSSHCommand, data_storage, host="slow.example", password="x", connect_timeout=1)
    started = time.monotonic()
    assert action.run({"command": "true"}) is None
    assert "DNS lookup timed out" in action.error_message
    assert time.monotonic() - started < 3


def test_dns_failure(data_storage):
    action = _action(RunSSHCommand, data_storage, host="host.invalid", password="x", connect_timeout=5)
    assert action.run({"command": "true"}) is None
    assert "Unable to resolve host.invalid" in action.error_message


def _reformat(openssh_pem: str, fmt, encryption=None) -> str:
    key = serialization.load_ssh_private_key(openssh_pem.encode(), None)
    return key.private_bytes(serialization.Encoding.PEM, fmt, encryption or serialization.NoEncryption()).decode()


def test_pkcs8_ed25519_key(ssh_server, data_storage):
    pkcs8 = _reformat(ssh_server["private_key"], serialization.PrivateFormat.PKCS8)
    assert "BEGIN PRIVATE KEY" in pkcs8
    action = _action(RunSSHCommand, data_storage, **_config(ssh_server, private_key=pkcs8))
    assert action.run({"command": "echo ok"})["stdout"] == "ok\n"


def test_encrypted_openssh_key():
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = rsa_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        serialization.BestAvailableEncryption(b"pass"),
    ).decode()
    with pytest.raises(SSHExecutionError, match="passphrase"):
        load_private_key(pem, None)
    assert isinstance(load_private_key(pem, "pass"), paramiko.RSAKey)


def test_passphrase_for_unencrypted_key(ssh_server):
    assert isinstance(load_private_key(ssh_server["private_key"], "unused"), paramiko.Ed25519Key)


def test_wrong_passphrase():
    pem = (
        rsa.generate_private_key(public_exponent=65537, key_size=2048)
        .private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(b"pass"),
        )
        .decode()
    )
    with pytest.raises(SSHExecutionError, match="wrong passphrase"):
        load_private_key(pem, "nope")


def test_unsupported_key_type():
    pem = (
        dsa.generate_private_key(key_size=2048)
        .private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
        .decode()
    )
    with pytest.raises(SSHExecutionError, match="Unsupported private key type"):
        load_private_key(pem, None)
