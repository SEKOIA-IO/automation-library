from functools import cached_property

from ldap3 import Connection, Server
from ldap3.utils.conv import escape_filter_chars
from sekoia_automation.action import Action

from microsoft_ad.models.common_models import MicrosoftADModule


class MicrosoftADAction(Action):
    module: MicrosoftADModule

    @cached_property
    def client(self):
        server = Server(
            host=self.module.configuration.servername,
            port=636,
            use_ssl=True,
        )
        conn = Connection(
            server,
            auto_bind=True,
            user=self.module.configuration.admin_username,
            password=self.module.configuration.admin_password,
        )

        return conn

    def search_userdn_query(self, username, basedn, display_name=None):
        safe_username = escape_filter_chars(username)
        or_filter = f"(|(samaccountname={safe_username})(userPrincipalName={safe_username})(mail={safe_username})(givenName={safe_username}))"

        if display_name is not None:
            safe_display_name = escape_filter_chars(display_name)
            search_filter = f"(&{or_filter}(displayName={safe_display_name}))"
        else:
            search_filter = or_filter

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
