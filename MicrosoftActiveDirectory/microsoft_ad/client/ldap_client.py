from functools import cached_property

from ldap3 import Connection, Server

from microsoft_ad.models.common_models import MicrosoftADModule


class LDAPClient:
    module: MicrosoftADModule

    _ldap_client: Connection | None = None

    @cached_property
    def ldap_server(self) -> Server:
        return Server(
            host=self.module.configuration.servername,
            port=636,
            use_ssl=True,
        )

    def _create_ldap_connection(self) -> Connection:
        return Connection(
            self.ldap_server,
            auto_bind=True,
            user=self.module.configuration.admin_username,
            password=self.module.configuration.admin_password,
        )

    @property
    def ldap_client(self) -> Connection:
        if self._ldap_client is None:
            self._ldap_client = self._create_ldap_connection()
        return self._ldap_client

    @ldap_client.setter
    def ldap_client(self, value: Connection) -> None:
        self._ldap_client = value

def _reset_ldap_connection(self) -> None:
    if self._ldap_client is not None:
        try:
            self._ldap_client.unbind()
        finally:
            self._ldap_client = None
