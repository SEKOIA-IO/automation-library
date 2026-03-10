from functools import cached_property

from ldap3 import Connection, Server

from microsoft_ad.models.common_models import MicrosoftADModule


class LDAPClient:
    module: MicrosoftADModule

    @cached_property
    def ldap_server(self) -> Server:
        return Server(
            host=self.module.configuration.servername,
            port=636,
            use_ssl=True,
        )

    @cached_property
    def ldap_client(self) -> Connection:
        return Connection(
            self.ldap_server,
            auto_bind=True,
            user=self.module.configuration.admin_username,
            password=self.module.configuration.admin_password,
        )
