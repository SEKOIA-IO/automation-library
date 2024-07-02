from sekoia_automation.action import GenericAPIAction

base_url = "api/v1/"


GetCommunity = type(
    "GetCommunity",
    (GenericAPIAction,),
    {
        "verb": "get",
        "endpoint": base_url + "communities/{uuid}",
        "query_parameters": [],
    },
)
