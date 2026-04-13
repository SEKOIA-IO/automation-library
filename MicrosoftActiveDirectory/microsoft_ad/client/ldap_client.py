import ssl
import tempfile
import os
from typing import Any
from functools import cached_property
from ldap3 import Server, Connection, Tls

from microsoft_ad.models.common_models import MicrosoftADModule


class LDAPClient:
    module: MicrosoftADModule

    def log(self, message: str, level: str = "info") -> None:
        """No-op fallback used when LDAPClient is instantiated without the Sekoia SDK (e.g. tests)."""
        pass

    def _build_tls(self) -> Tls:
        """Build the TLS configuration from module settings.

        Priority order:
        1. skip_tls_verify=True  -> CERT_NONE (no verification, testing only)
        2. ca_certificate set    -> CERT_REQUIRED with custom CA
        3. Default               -> CERT_REQUIRED with system CA bundle

        ssl.PROTOCOL_TLS is always forced to ensure compatibility with AD servers
        that require TLS 1.2+. An optional cipher suite can be set via tls_ciphers.
        """
        config = self.module.configuration
        kwargs: dict[str, Any] = {"version": ssl.PROTOCOL_TLS}
        if config.tls_ciphers:
            kwargs["ciphers"] = config.tls_ciphers

        if config.skip_tls_verify:
            self.log("[LDAPClient._build_tls] TLS mode: CERT_NONE (skip_tls_verify=True)", level="warning")
            return Tls(validate=ssl.CERT_NONE, **kwargs)

        if config.ca_certificate:
            self.log("[LDAPClient._build_tls] TLS mode: CERT_REQUIRED with custom CA certificate", level="debug")
            return Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=self._ca_cert_path, **kwargs)

        self.log("[LDAPClient._build_tls] TLS mode: CERT_REQUIRED with system CA bundle", level="debug")
        return Tls(validate=ssl.CERT_REQUIRED, **kwargs)

    @cached_property
    def _ca_cert_path(self) -> str | None:
        """Write the CA certificate to a temporary PEM file and return its path.

        The file is created once (cached_property) and deleted after the connection
        attempt in ldap_client. Returns None if no ca_certificate is configured.
        """
        ca_cert = self.module.configuration.ca_certificate
        if not ca_cert:
            return None
        with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
            f.write(ca_cert)
            path = f.name
        self.log(f"[LDAPClient._ca_cert_path] CA cert written to: {path}", level="debug")
        return path

    @cached_property
    def ldap_server(self) -> Server:
        config = self.module.configuration
        self.log(
            f"[LDAPClient.ldap_server] Building Server — host={config.servername} port={config.port} use_ssl=True",
            level="debug",
        )
        server = Server(
            host=config.servername,
            port=config.port,
            use_ssl=True,
            tls=self._build_tls(),
        )
        self.log(f"[LDAPClient.ldap_server] Server object created: {server}", level="debug")
        return server

    @cached_property
    def ldap_client(self) -> Connection:
        cfg = self.module.configuration
        self.log(
            f"[LDAPClient.ldap_client] Opening Connection — user={cfg.admin_username} auto_bind=True",
            level="debug",
        )
        try:
            conn = Connection(
                self.ldap_server,
                auto_bind=True,
                user=cfg.admin_username,
                password=cfg.admin_password,
            )
        except Exception as exc:
            self.log(
                f"[LDAPClient.ldap_client] Connection failed ({type(exc).__name__}): {exc}",
                level="error",
            )
            raise
        finally:
            # Clean up the temporary CA file after the connection attempt
            ca_path = self.__dict__.get("_ca_cert_path")
            if ca_path and os.path.exists(ca_path):
                os.unlink(ca_path)
                self.log(f"[LDAPClient.ldap_client] Temp CA file removed: {ca_path}", level="debug")

        self.log(
            f"[LDAPClient.ldap_client] Connection bound={conn.bound} tls_started={conn.tls_started}",
            level="debug",
        )
        self.log(f"[LDAPClient.ldap_client] Bind result: {conn.result}", level="debug")
        return conn
