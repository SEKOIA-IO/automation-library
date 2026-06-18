from ldap3 import Connection, Server
from ldap3.core.exceptions import LDAPException
from ldap3.utils.conv import escape_filter_chars
from sekoia_automation.action import Action

from microsoft_ad.models.common_models import MicrosoftADModule


class MicrosoftADAction(Action):
    module: MicrosoftADModule
    _override_client: Connection | None = None

    @property
    def client(self):
        # Return override client if set, otherwise create/get default client
        if self._override_client is not None:
            return self._override_client

        # Use cached property pattern manually
        if not hasattr(self, "_default_client"):
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
            self._default_client = conn

        return self._default_client

    @client.setter
    def client(self, value: Connection | None):
        """Set the override client."""
        self._override_client = value

    def client_for(self, host: str | None = None) -> Connection:
        """Create a client connection to the specified host or use the default client."""
        if host is None:
            return self.client

        server = Server(
            host=host,
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

    def _get_forest_root_dn(self, basedn: str | None = None, client: Connection | None = None) -> str | None:
        """Extract the forest root DN from RootDSE."""
        target_client = client or self.client
        try:
            target_client.search(
                search_base="",
                search_filter="(objectClass=*)",
                attributes=["rootDomainNamingContext"],
                search_scope="BASE",
            )
            for entry in target_client.response:
                if isinstance(entry, dict) and entry.get("type") == "searchResEntry":
                    root_dn = entry.get("attributes", {}).get("rootDomainNamingContext")
                    if root_dn:
                        if isinstance(root_dn, list):
                            return root_dn[0]
                        return root_dn
        except LDAPException as e:
            self.log(f"Failed to get forest root DN: {e}", level="debug")
        return None

    def _get_child_domains(self, forest_root_dn: str, client: Connection | None = None) -> list[str]:
        """Discover child domains in the forest."""
        target_client = client or self.client
        child_domains = []
        try:
            # Search for child domains in the Partitions container
            partitions_base = f"CN=Partitions,CN=Configuration,{forest_root_dn}"
            target_client.search(
                search_base=partitions_base,
                search_filter="(&(objectClass=crossRef)(systemFlags:1.2.840.113556.1.4.803:=2))",
                attributes=["nCName"],
                search_scope="SUBTREE",
            )

            for entry in target_client.response:
                if isinstance(entry, dict) and entry.get("type") == "searchResEntry":
                    nc_name = entry.get("attributes", {}).get("nCName")
                    if nc_name:
                        # nCName can be a list or a string
                        domain_dn = nc_name[0] if isinstance(nc_name, list) else nc_name
                        if domain_dn and domain_dn != forest_root_dn:
                            child_domains.append(domain_dn)

            self.log(f"Found {len(child_domains)} child domain(s)", level="debug")
        except LDAPException as e:
            self.log(f"Failed to discover child domains: {e}", level="debug")

        return child_domains

    def _perform_search(
        self,
        search_filter: str,
        basedn: str,
        raise_on_error: bool = False,
        client: Connection | None = None,
    ) -> list[list]:
        """Perform a single LDAP search and return results."""
        target_client = client or self.client
        users_query = []

        try:
            target_client.search(
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

        for entry in target_client.response:
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

    def search_userdn_query(self, username, basedn, email=None, search_child_domains=True, domain_controller=None):
        has_username = bool(username)
        has_email = bool(email)

        if not has_username and not has_email:
            raise ValueError("At least one of 'username' or 'email' must be provided")

        if has_username:
            safe_username = escape_filter_chars(username)
            or_filter = (
                f"(|(samaccountname={safe_username})(userPrincipalName={safe_username})"
                f"(mail={safe_username})(givenName={safe_username}))"
            )

        if has_username and has_email:
            safe_email = escape_filter_chars(email)
            search_filter = f"(&{or_filter}(mail={safe_email}))"
        elif has_username:
            search_filter = or_filter
        else:
            safe_email = escape_filter_chars(email)
            search_filter = f"(mail={safe_email})"

        # Use specified domain controller or default client
        client = self.client_for(domain_controller)

        self.log(f"Starting search in {basedn} for {username}", level="debug")

        # First, try searching in the specified basedn (raise exceptions on error)
        users_query = self._perform_search(search_filter, basedn, raise_on_error=True, client=client)

        # If no users found and search_child_domains is enabled, try child domains (silently ignore errors)
        if not users_query and search_child_domains:
            self.log(f"No users found in {basedn}, searching child domains", level="debug")

            forest_root_dn = self._get_forest_root_dn(basedn, client=client)
            if forest_root_dn:
                child_domains = self._get_child_domains(forest_root_dn, client=client)

                for child_domain in child_domains:
                    self.log(f"Searching in child domain: {child_domain}", level="debug")
                    child_results = self._perform_search(
                        search_filter, child_domain, raise_on_error=False, client=client
                    )
                    users_query.extend(child_results)

                    if users_query:
                        self.log(f"Found user(s) in child domain {child_domain}", level="debug")
                        break

        self.log(f"Search finished. {len(users_query)} user(s) found.", level="debug")

        return users_query
