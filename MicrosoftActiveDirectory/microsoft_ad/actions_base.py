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

    def get_client(self, servername: str | None = None) -> Connection:
        if not servername or servername == self.module.configuration.servername:
            return self.client

        server = Server(
            host=servername,
            port=636,
            use_ssl=True,
        )
        return Connection(
            server,
            auto_bind=True,
            user=self.module.configuration.admin_username,
            password=self.module.configuration.admin_password,
        )

    def _get_forest_root_dn(self, client: Connection) -> str | None:
        """Extract the forest root DN from RootDSE."""
        try:
            client.search(
                search_base="",
                search_filter="(objectClass=*)",
                attributes=["rootDomainNamingContext"],
            )
            for entry in client.response:
                if isinstance(entry, dict) and entry.get("type") == "searchResEntry":
                    root_dn = entry.get("attributes", {}).get("rootDomainNamingContext")
                    if root_dn:
                        if isinstance(root_dn, list):
                            return root_dn[0]
                        return root_dn
        except Exception as e:
            self.log(f"Failed to get forest root DN: {e}", level="debug")
        return None

    def _get_child_domains(self, client: Connection, forest_root_dn: str) -> list[str]:
        """Discover child domains in the forest."""
        child_domains = []
        try:
            # Search for domain objects under the forest root
            client.search(
                search_base=forest_root_dn,
                search_filter="(objectClass=domain)",
                attributes=["distinguishedName"],
                search_scope="SUBTREE",
            )
            
            for entry in client.response:
                if isinstance(entry, dict) and entry.get("type") == "searchResEntry":
                    dn = entry.get("dn")
                    if dn and dn != forest_root_dn:
                        child_domains.append(dn)
            
            self.log(f"Found {len(child_domains)} child domain(s)", level="debug")
        except Exception as e:
            self.log(f"Failed to discover child domains: {e}", level="debug")
        
        return child_domains

    def _perform_search(
        self,
        client: Connection,
        search_filter: str,
        basedn: str,
        username: str | None = None,
        raise_on_error: bool = False,
    ) -> list[list]:
        """Perform a single LDAP search and return results."""
        users_query = []
        
        try:
            client.search(
                search_base=basedn,
                search_filter=search_filter,
                attributes=["cn", "mail", "userAccountControl"],
            )
        except Exception as e:
            if raise_on_error:
                raise Exception(f"LDAP search failed in base {basedn}: {e}") from e
            else:
                self.log(f"LDAP search failed in base {basedn}: {e}", level="debug")
                return users_query

        for entry in client.response:
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

        return users_query

    def search_userdn_query(self, username, basedn, email=None, servername=None, search_child_domains=True):
        has_username = bool(username)
        has_email = bool(email)

        if not has_username and not has_email:
            raise ValueError("At least one of 'username' or 'email' must be provided")

        if has_username:
            safe_username = escape_filter_chars(username)
            or_filter = f"(|(samaccountname={safe_username})(userPrincipalName={safe_username})(mail={safe_username})(givenName={safe_username}))"

        if has_username and has_email:
            safe_email = escape_filter_chars(email)
            search_filter = f"(&{or_filter}(mail={safe_email}))"
        elif has_username:
            search_filter = or_filter
        else:
            safe_email = escape_filter_chars(email)
            search_filter = f"(mail={safe_email})"

        self.log(f"Starting search in {basedn} for {username}", level="debug")

        client = self.get_client(servername)
        
        # First, try searching in the specified basedn (raise exceptions on error)
        users_query = self._perform_search(client, search_filter, basedn, username, raise_on_error=True)
        
        # If no users found and search_child_domains is enabled, try child domains (silently ignore errors)
        if not users_query and search_child_domains:
            self.log(f"No users found in {basedn}, searching child domains", level="debug")
            
            forest_root_dn = self._get_forest_root_dn(client)
            if forest_root_dn:
                child_domains = self._get_child_domains(client, forest_root_dn)
                
                for child_domain in child_domains:
                    self.log(f"Searching in child domain: {child_domain}", level="debug")
                    child_results = self._perform_search(client, search_filter, child_domain, username, raise_on_error=False)
                    users_query.extend(child_results)
                    
                    if users_query:
                        self.log(f"Found user(s) in child domain {child_domain}", level="debug")
                        break

        self.log(f"Search finished. {len(users_query)} user(s) found.", level="debug")

        return users_query
