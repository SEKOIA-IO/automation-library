import base64
import hashlib
import io
import time
from dataclasses import dataclass

import paramiko

from ssh_remote.models import SSHModuleConfiguration

# Keep results small enough for the playbook engine
MAX_OUTPUT_BYTES = 1024 * 1024
READ_CHUNK = 32 * 1024


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
    # Keys pasted in a single-line field often arrive with literal "\n"
    if "\\n" in data and "\n" not in data.strip():
        data = data.replace("\\n", "\n")
    data = data.strip() + "\n"

    errors = []
    for key_class in (paramiko.Ed25519Key, paramiko.ECDSAKey, paramiko.RSAKey):
        try:
            return key_class.from_private_key(io.StringIO(data), password=passphrase or None)
        except paramiko.PasswordRequiredException:
            raise SSHExecutionError("The private key is encrypted: set its passphrase in the account")
        except (paramiko.SSHException, ValueError) as exc:
            errors.append(f"{key_class.__name__}: {exc}")
    raise SSHExecutionError("Unable to load the private key (" + "; ".join(errors) + ")")


class _FingerprintPolicy(paramiko.MissingHostKeyPolicy):
    """Accept the host key only if it matches the pinned fingerprint (when one is set)."""

    def __init__(self, expected: str | None):
        self.expected = (expected or "").strip()
        self.observed: str | None = None

    def missing_host_key(self, _client, hostname, key):
        self.observed = fingerprint(key)
        if self.expected and self.observed.rstrip("=") != self.expected.rstrip("="):
            raise SSHExecutionError(f"Host key mismatch for {hostname}: expected {self.expected}, got {self.observed}")


def _append(buffer: bytearray, chunk: bytes) -> bool:
    """Append within the size limit; return True if part of the chunk was dropped."""
    room = MAX_OUTPUT_BYTES - len(buffer)
    buffer += chunk[: max(room, 0)]
    return len(chunk) > room


def _decode(buffer: bytearray, truncated: bool) -> str:
    text = buffer.decode("utf-8", errors="replace")
    if truncated:
        text += f"\n[output truncated to {MAX_OUTPUT_BYTES} bytes]"
    return text


class SSHRunner:
    def __init__(self, config: SSHModuleConfiguration, host: str | None = None):
        self.config = config
        self.host = host or config.host

    def _connect(self) -> tuple[paramiko.SSHClient, _FingerprintPolicy]:
        if not self.config.private_key and not self.config.password:
            raise SSHExecutionError("Set either a private key or a password in the account")

        pkey = load_private_key(self.config.private_key, self.config.passphrase) if self.config.private_key else None

        policy = _FingerprintPolicy(self.config.host_key_fingerprint)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(policy)
        try:
            client.connect(
                hostname=self.host,
                port=self.config.port,
                username=self.config.username,
                pkey=pkey,
                password=None if pkey else self.config.password,
                timeout=self.config.connect_timeout,
                banner_timeout=self.config.connect_timeout,
                auth_timeout=self.config.connect_timeout,
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
        try:
            channel = client.get_transport().open_session()
            channel.exec_command(command)

            if stdin_data is not None:
                channel.sendall(stdin_data.encode())
                channel.shutdown_write()

            stdout, stderr = bytearray(), bytearray()
            out_truncated = err_truncated = False
            deadline = time.monotonic() + timeout

            while True:
                activity = False
                if channel.recv_ready():
                    activity = True
                    out_truncated |= _append(stdout, channel.recv(READ_CHUNK))
                if channel.recv_stderr_ready():
                    activity = True
                    err_truncated |= _append(stderr, channel.recv_stderr(READ_CHUNK))
                if channel.exit_status_ready() and not channel.recv_ready() and not channel.recv_stderr_ready():
                    break
                if time.monotonic() > deadline:
                    channel.close()
                    raise SSHExecutionError(f"Execution on {self.host} timed out after {timeout}s")
                if not activity:
                    time.sleep(0.1)

            return ExecutionResult(
                host=self.host,
                exit_code=channel.recv_exit_status(),
                stdout=_decode(stdout, out_truncated),
                stderr=_decode(stderr, err_truncated),
                host_key_fingerprint=policy.observed or "",
            )
        finally:
            client.close()
