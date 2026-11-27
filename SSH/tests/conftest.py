"""A minimal in-process SSH server so the tests exercise the real SSH path.

It accepts one public key (and optionally one password) and runs the requested
command locally with /bin/sh, piping stdin/stdout/stderr through the channel.
"""

import socket
import subprocess
import threading
import time
from shutil import rmtree
from tempfile import mkdtemp

import paramiko
import pytest
from sekoia_automation import constants

from ssh_remote.client import fingerprint


@pytest.fixture
def data_storage():
    original_storage = constants.DATA_STORAGE
    constants.DATA_STORAGE = mkdtemp()
    yield constants.DATA_STORAGE
    rmtree(constants.DATA_STORAGE)
    constants.DATA_STORAGE = original_storage


class _Server(paramiko.ServerInterface):
    def __init__(self, allowed_key: paramiko.PKey, password: str):
        self.allowed_key = allowed_key
        self.password = password
        self.command: bytes | None = None
        self.event = threading.Event()

    def check_channel_request(self, kind, chanid):
        return paramiko.OPEN_SUCCEEDED if kind == "session" else paramiko.OPEN_FAILED_ADMINISTRATIVELY_PROHIBITED

    def get_allowed_auths(self, username):
        return "publickey,password"

    def check_auth_publickey(self, username, key):
        if username == "tester" and key.asbytes() == self.allowed_key.asbytes():
            return paramiko.AUTH_SUCCESSFUL
        return paramiko.AUTH_FAILED

    def check_auth_password(self, username, password):
        return paramiko.AUTH_SUCCESSFUL if username == "tester" and password == self.password else paramiko.AUTH_FAILED

    def check_channel_exec_request(self, channel, command):
        if command == b"__hang__":
            # Simulate a server that never answers the exec request
            time.sleep(5)
        self.command = command
        self.event.set()
        return True


def _serve(sock: socket.socket, host_key, client_key, password, stop: threading.Event):
    sock.settimeout(0.5)
    while not stop.is_set():
        try:
            conn, _ = sock.accept()
        except TimeoutError:
            continue
        threading.Thread(target=_handle, args=(conn, host_key, client_key, password), daemon=True).start()


def _handle(conn, host_key, client_key, password):
    transport = paramiko.Transport(conn)
    transport.add_server_key(host_key)
    server = _Server(client_key, password)
    try:
        transport.start_server(server=server)
        channel = transport.accept(10)
        if channel is None or not server.event.wait(10):
            return
        proc = subprocess.Popen(
            ["/bin/sh", "-c", server.command.decode()],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        def pump_stdin():
            while True:
                data = channel.recv(4096)
                if not data:
                    break
                proc.stdin.write(data)
            proc.stdin.close()

        threading.Thread(target=pump_stdin, daemon=True).start()
        out_thread = threading.Thread(target=lambda: channel.sendall(proc.stdout.read()), daemon=True)
        out_thread.start()
        err = proc.stderr.read()
        out_thread.join()
        channel.sendall_stderr(err)
        channel.send_exit_status(proc.wait())
        channel.close()
    except Exception:
        pass
    finally:
        transport.close()


@pytest.fixture(scope="session")
def ssh_server():
    host_key = paramiko.Ed25519Key.from_private_key(_new_ed25519_pem())
    client_key_pem = _new_ed25519_pem().getvalue()
    client_key = paramiko.Ed25519Key.from_private_key(__import__("io").StringIO(client_key_pem))
    password = "s3cret"

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    sock.listen(10)
    stop = threading.Event()
    thread = threading.Thread(target=_serve, args=(sock, host_key, client_key, password, stop), daemon=True)
    thread.start()

    yield {
        "host": "127.0.0.1",
        "port": sock.getsockname()[1],
        "private_key": client_key_pem,
        "password": password,
        "host_key_fingerprint": fingerprint(host_key),
    }

    stop.set()
    thread.join()
    sock.close()


def _new_ed25519_pem():
    """Generate an OpenSSH-format Ed25519 private key (paramiko can't generate Ed25519)."""
    import io

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    pem = Ed25519PrivateKey.generate().private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()
    )
    return io.StringIO(pem.decode())
