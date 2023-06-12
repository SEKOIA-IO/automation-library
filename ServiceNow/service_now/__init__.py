from requests.auth import _basic_auth_str as basic_auth
from sekoia_automation.action import GenericAPIAction

base_url = ""


class ServiceNowAction(GenericAPIAction):
    def get_headers(self):
        headers = {"Accept": "application/json"}

        username = self.module.configuration.get("username")
        password = self.module.configuration.get("password")
        headers["Authorization"] = basic_auth(username, password)

        return headers


GetTable = type(
    "GetTable",
    (ServiceNowAction,),
    {
        "verb": "get",
        "endpoint": base_url + "table/{table_name}",
        "query_parameters": [],
    },
)
