from ldap3 import Connection, Server

from microsoft_ad.models.common_models import MicrosoftADModule


class LDAPClient:
    @classmethod
    def from_module(cls, module: MicrosoftADModule) -> Connection:
        """Create a connection using the module's default configuration."""
        server = Server(
            host=module.configuration.servername,
            port=636,
            use_ssl=True,
        )
        return Connection(
            server,
            auto_bind=True,
            user=module.configuration.admin_username,
            password=module.configuration.admin_password,
        )

    @classmethod
    def for_domain_controller(cls, host: str, module: MicrosoftADModule) -> Connection:
        """Create a connection to a specific domain controller host."""
        server = Server(
            host=host,
            port=636,
            use_ssl=True,
        )
        return Connection(
            server,
            auto_bind=True,
            user=module.configuration.admin_username,
            password=module.configuration.admin_password,
        )
