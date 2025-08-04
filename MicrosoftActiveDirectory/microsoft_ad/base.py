from functools import cached_property
from ldap3 import Server, Connection

from pydantic.v1 import BaseModel, Field
from sekoia_automation.action import Action
from sekoia_automation.module import Module


class MicrosoftADConfiguration(BaseModel):
    servername: str = Field(..., description="Remote machine IP or Name")
    admin_username: str = Field(..., description="Admin username")
    admin_password: str = Field(..., secret=True, description="Admin password")  # type: ignore


class MicrosoftADModule(Module):
    configuration: MicrosoftADConfiguration


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

    def search_userdn_query(self, username, basedn):
        SEARCHFILTER = (
            f"(|(samaccountname={username})(userPrincipalName={username})(mail={username})(givenName={username}))"
        )

        try:
            self.client.search(
                search_base=basedn, search_filter=SEARCHFILTER, attributes=["cn", "mail", "userAccountControl"]
            )
        except:
            raise Exception(f"Failed to search in this base {basedn}")

        users_query = []
        for entry in self.client.response:
            if entry.get("dn") and entry.get("attributes"):
                if entry.get("attributes").get("cn"):
                    users_query.append([entry.get("dn"), entry.get("attributes").get("userAccountControl")])

        return users_query


class UserAccountArguments(BaseModel):
    basedn: str | None = Field(None, description="")
    username: str | None = Field(
        None,
        description="",
    )


class ResetPassUserArguments(UserAccountArguments):
    new_password: str | None = Field(
        None,
        description="",
    )
