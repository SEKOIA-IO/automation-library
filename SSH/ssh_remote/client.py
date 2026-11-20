import base64
import hashlib
import io
import re
import select
import socket
import threading
from dataclasses import dataclass

import paramiko
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa

from ssh_remote.models import SSHModuleConfiguration

# Keep results small enough for the playbook engine
MAX_OUTPUT_BYTES = 1024 * 1024
READ_CHUNK = 32 * 1024
# Upper bound of a wait for output, to recheck the exit status
POLL_INTERVAL = 0.5


class SSHExecutionError(Exception):
    pass


@dataclass
class ExecutionResult:
    host: str
    exit_code: int
    stdout: str
    stderr: str
    host_key_fingerprint: str

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "host_key_fingerprint": self.host_key_fingerprint,
        }


def fingerprint(key: paramiko.PKey) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    return "SHA256:" + base64.b64encode(digest).decode().rstrip("=")


def load_private_key(data: str, passphrase: str | None) -> paramiko.PKey:
    """Load an OpenSSH, PKCS#1, SEC1 or PKCS#8 private key (RSA, ECDSA or Ed25519)."""
    # Keys pasted in a single-line field often arrive with literal "\n"
    if "\\n" in data and "\n" not in data.strip():
        data = data.replace("\\n", "\n")
    raw = (data.strip() + "\n").encode()
    password = passphrase.encode() if passphrase else None

    loader = (
        serialization.load_ssh_private_key
        if b"BEGIN OPENSSH PRIVATE KEY" in raw
        else serialization.load_pem_private_key
    )
    try:
        try:
            key = loader(raw, password)
        except TypeError:
            # Either the key is encrypted and no passphrase was given,
            # or a passphrase was given for a key that isn't encrypted
            if password is None:
                raise SSHExecutionError("The private key is encrypted: set its passphrase in the account")
            key = loader(raw, None)
    except SSHExecutionError:
        raise
    except Exception as exc:
        raise SSHExecutionError(f"Unable to load the private key (wrong passphrase or unsupported format): {exc}")

    key_class: type[paramiko.PKey]
    if isinstance(key, ed25519.Ed25519PrivateKey):
        key_class = paramiko.Ed25519Key
    elif isinstance(key, ec.EllipticCurvePrivateKey):
        key_class = paramiko.ECDSAKey
    elif isinstance(key, rsa.RSAPrivateKey):
        key_class = paramiko.RSAKey
    else:
        raise SSHExecutionError(f"Unsupported private key type: {type(key).__name__}. Use RSA, ECDSA or Ed25519")

    # Paramiko reads every supported key type in the OpenSSH format
    openssh = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.OpenSSH, serialization.NoEncryption()
    )
    return key_class.from_private_key(io.StringIO(openssh.decode()))


def _normalise_fingerprint(value: str) -> str:
    value = value.strip().rstrip("=")
    if value[:7].upper() == "SHA256:":
        value = value[7:]
    return "SHA256:" + value


def parse_fingerprints(value: str | None) -> set[str]:
    return {_normalise_fingerprint(item) for item in re.split(r"[\s,]+", value or "") if item}


class _FingerprintPolicy(paramiko.MissingHostKeyPolicy):
    """Accept the host key only if it matches a pinned fingerprint, unless explicitly told to accept any key."""

    def __init__(self, expected: set[str], accept_unknown: bool):
        self.expected = expected
        self.accept_unknown = accept_unknown
        self.observed: str | None = None

    def missing_host_key(self, _client, hostname, key):
        self.observed = fingerprint(key)
        if self.expected:
            if self.observed not in self.expected:
                raise SSHExecutionError(
                    f"Host key mismatch for {hostname}: got {self.observed}, "
                    f"which is not one of the pinned fingerprints"
                )
        elif not self.accept_unknown:
            raise SSHExecutionError(
                f"The host key of {hostname} is not pinned. If {self.observed} is the expected fingerprint, "
                f"set it in the account's host key fingerprints (or enable accept_unknown_host_keys)"
            )


def resolve_host(host: str, port: int, timeout: float) -> str:
    """Resolve the host to an IP address within the timeout (getaddrinfo itself has no timeout)."""
    result: dict = {}

    def lookup():
        try:
            result["address"] = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)[0][4][0]
        except Exception as exc:
            result["error"] = exc

    # Daemon thread: a stuck resolver must not keep the process alive
    thread = threading.Thread(target=lookup, daemon=True)
    thread.start()
    thread.join(timeout)
    if thread.is_alive():
        raise SSHExecutionError(f"Unable to resolve {host}: DNS lookup timed out after {timeout}s")
    if "error" in result:
        raise SSHExecutionError(f"Unable to resolve {host}: {result['error']}")
    return result["address"]


def _append(buffer: bytearray, chunk: bytes) -> bool:
    """Append within the size limit; return True if part of the chunk was dropped."""
    room = MAX_OUTPUT_BYTES - len(buffer)
    buffer += chunk[: max(room, 0)]
    return len(chunk) > room


def _send_stdin(channel: paramiko.Channel, data: str) -> None:
    try:
        channel.sendall(data.encode())
        # Close stdin, so interpreters reading it until EOF don't hang
        channel.shutdown_write()
    except Exception:
        # The channel was closed (command exited without reading its input, or timeout):
        # the reading loop reports the outcome
        pass


def _decode(buffer: bytearray, truncated: bool) -> str:
    text = buffer.decode("utf-8", errors="replace")
    if truncated:
        text += f"\n[output truncated to {MAX_OUTPUT_BYTES} bytes]"
    return text


class SSHRunner:
    def __init__(self, config: SSHModuleConfiguration, host: str | None = None):
        self.config = config
        self.host = self._check_host(host) if host else config.host

    def _check_host(self, host: str) -> str:
        host = host.strip()
        allowed = {config_host.strip().lower() for config_host in self.config.allowed_hosts}
        if host.lower() != self.config.host.strip().lower() and host.lower() not in allowed:
            raise SSHExecutionError(
                f"The host {host} is not allowed: add it to the account's allowed hosts to run actions on it"
            )
        return host

    def _connect(self) -> tuple[paramiko.SSHClient, _FingerprintPolicy]:
        if not self.config.private_key and not self.config.password:
            raise SSHExecutionError("Set either a private key or a password in the account")

        pkey = load_private_key(self.config.private_key, self.config.passphrase) if self.config.private_key else None
        address = resolve_host(self.host, self.config.port, self.config.connect_timeout)

        policy = _FingerprintPolicy(
            parse_fingerprints(self.config.host_key_fingerprint), self.config.accept_unknown_host_keys
        )
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(policy)
        try:
            client.connect(
                hostname=address,
                port=self.config.port,
                username=self.config.username,
                pkey=pkey,
                password=None if pkey else self.config.password,
                timeout=self.config.connect_timeout,
                banner_timeout=self.config.connect_timeout,
                auth_timeout=self.config.connect_timeout,
                channel_timeout=self.config.connect_timeout,
                allow_agent=False,
                look_for_keys=False,
            )
        except SSHExecutionError:
            client.close()
            raise
        except paramiko.AuthenticationException as exc:
            client.close()
            raise SSHExecutionError(f"Authentication failed for {self.config.username}@{self.host}: {exc}")
        except Exception as exc:
            client.close()
            raise SSHExecutionError(f"Unable to connect to {self.host}:{self.config.port}: {exc}")
        return client, policy

    def run(self, command: str, stdin_data: str | None = None, timeout: int = 300) -> ExecutionResult:
        client, policy = self._connect()

        # Paramiko waits without a timeout in some calls (e.g. exec_command), so a watchdog closes the
        # connection when the deadline passes. That unblocks every pending call, which then raises.
        timed_out = threading.Event()

        def on_timeout():
            timed_out.set()
            client.close()

        watchdog = threading.Timer(timeout, on_timeout)
        watchdog.daemon = True
        watchdog.start()
        try:
            try:
                return self._execute(client, policy, command, stdin_data, timed_out)
            except SSHExecutionError:
                raise
            except Exception as exc:
                if timed_out.is_set():
                    raise SSHExecutionError(f"Execution on {self.host} timed out after {timeout}s")
                raise SSHExecutionError(f"SSH session with {self.host} failed: {exc}")
        finally:
            watchdog.cancel()
            client.close()

    def _execute(
        self,
        client: paramiko.SSHClient,
        policy: _FingerprintPolicy,
        command: str,
        stdin_data: str | None,
        timed_out: threading.Event,
    ) -> ExecutionResult:
        transport = client.get_transport()
        if transport is None:
            raise SSHExecutionError(f"The SSH connection to {self.host} was closed")
        channel = transport.open_session(timeout=self.config.connect_timeout)
        channel.exec_command(command)

        # Feed stdin from a separate thread: if the remote writes more output than the SSH window holds
        # before reading all its input, sending and reading in the same thread would deadlock
        if stdin_data is None:
            # Nothing to send: close stdin right away, so commands reading it until EOF don't hang
            channel.shutdown_write()
        else:
            threading.Thread(target=_send_stdin, args=(channel, stdin_data), daemon=True).start()

        stdout, stderr = bytearray(), bytearray()
        out_truncated = err_truncated = False
        while True:
            if channel.recv_ready():
                out_truncated |= _append(stdout, channel.recv(READ_CHUNK))
            if channel.recv_stderr_ready():
                err_truncated |= _append(stderr, channel.recv_stderr(READ_CHUNK))
            if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                break
            if not channel.recv_ready() and not channel.recv_stderr_ready():
                # The channel's file descriptor is signalled when stdout or stderr data arrives or the channel
                # closes. The exit status alone does not signal it, hence the bounded wait.
                select.select([channel], [], [], POLL_INTERVAL)

        # Closing the connection also marks the exit status as ready, so check the watchdog first
        if timed_out.is_set():
            raise TimeoutError()

        return ExecutionResult(
            host=self.host,
            exit_code=channel.recv_exit_status(),
            stdout=_decode(stdout, out_truncated),
            stderr=_decode(stderr, err_truncated),
            host_key_fingerprint=policy.observed or "",
        )
