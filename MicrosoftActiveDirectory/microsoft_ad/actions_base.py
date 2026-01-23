from functools import cached_property
import ssl
import tempfile

from ldap3 import Server, Connection, Tls
from ldap3.utils.conv import escape_filter_chars

from sekoia_automation.action import Action

from microsoft_ad.models.common_models import MicrosoftADModule


class MicrosoftADAction(Action):
    module: MicrosoftADModule

    @cached_property
    def client(self):
        tls_config = None
        ca_cert = self.module.configuration.ca_certificate
        if ca_cert:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".pem", delete=False) as f:
                f.write(ca_cert)
                ca_file = f.name
            tls_config = Tls(validate=ssl.CERT_REQUIRED, ca_certs_file=ca_file)
        else:
            tls_config = Tls(validate=ssl.CERT_NONE)

        server = Server(
            host=self.module.configuration.servername,
            port=636,
            use_ssl=True,
            tls=tls_config,
        )
        conn = Connection(
            server,
            auto_bind=True,
            user=self.module.configuration.admin_username,
            password=self.module.configuration.admin_password,
        )

        return conn

    def search_userdn_query(self, username, basedn):
        safe_username = escape_filter_chars(username)
        search_filter = f"(|(samaccountname={safe_username})(userPrincipalName={safe_username})(mail={safe_username})(givenName={safe_username}))"

        self.log(f"Starting search in {basedn} for {username}", level="debug")

        try:
            self.client.search(
                search_base=basedn, search_filter=search_filter, attributes=["cn", "mail", "userAccountControl"]
            )
        except Exception as e:
            raise Exception(f"LDAP search failed in base {basedn}: {e}") from e

        users_query = []

        for entry in self.client.response:
            if isinstance(entry, dict) and entry.get("type") == "searchResEntry":
                dn = entry.get("dn")
                user_attributes = entry.get("attributes", {})
                account_control: int | list[int] | None = user_attributes.get("userAccountControl")

                self.log(f"Found user {dn} with userAccountControl param: {account_control}", level="debug")

                if dn and user_attributes.get("cn"):
                    account_control_final = None
                    if account_control is not None:
                        if isinstance(account_control, list):
                            account_control_final = int(account_control[0]) if len(account_control) > 0 else None
                        else:
                            account_control_final = account_control

                    users_query.append([dn, account_control_final])

        self.log(f"Search finished. {len(users_query)} user(s) found.", level="debug")

        return users_query
