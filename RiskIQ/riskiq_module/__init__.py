from requests.auth import _basic_auth_str as basic_auth
from sekoia_automation.action import GenericAPIAction

base_url = ""


class RiskIQAction(GenericAPIAction):
    def get_headers(self):
        api_key = self.module.configuration.get("api_key")
        api_secret = self.module.configuration.get("api_secret")
        return {
            "Accept": "application/json",
            "Authorization": basic_auth(api_key, api_secret),
        }


PdnsIPAction = type(
    "PdnsIPAction",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v0/pdns/data/ip",
        "query_parameters": ["ip", "max", "lastSeenAfter", "firstSeenBefore"],
    },
)

PdnsNameAction = type(
    "PdnsNameAction",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v0/pdns/data/name",
        "query_parameters": ["name", "type", "max", "lastSeenAfter", "firstSeenBefore"],
    },
)

PdnsHexAction = type(
    "PdnsHexAction",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v0/pdns/data/raw",
        "query_parameters": ["type", "max", "lastSeenAfter", "firstSeenBefore", "hex"],
    },
)

SslCertificatesByHostNameAction = type(
    "SslCertificatesByHostNameAction",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v1/ssl/cert/host",
        "query_parameters": ["host"],
    },
)

SslCertificatesBySerialNumberAction = type(
    "SslCertificatesBySerialNumberAction",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v1/ssl/cert/serial",
        "query_parameters": ["serial"],
    },
)

SslCertificateBySha1Action = type(
    "SslCertificateBySha1Action",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v1/ssl/cert/sha1",
        "query_parameters": ["sha1"],
    },
)

HostsByCertificateAction = type(
    "HostsByCertificateAction",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v1/ssl/host",
        "query_parameters": ["certSha1"],
    },
)

SslCertificatesByNameAction = type(
    "SslCertificatesByNameAction",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v1/ssl/cert/name",
        "query_parameters": ["name"],
    },
)

GetWhoisRecordsAssociatedWithAddress = type(
    "GetWhoisRecordsAssociatedWithAddress",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v0/whois/address",
        "query_parameters": ["address", "exact", "maxResults"],
    },
)

GetCurrentWhoisForDomain = type(
    "GetCurrentWhoisForDomain",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v0/whois/domain",
        "query_parameters": ["domain", "exact", "maxResults"],
    },
)

WhoisRecordsAssociatedWithEmailAddress = type(
    "WhoisRecordsAssociatedWithEmailAddress",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v0/whois/email",
        "query_parameters": ["email", "exact", "maxResults"],
    },
)

WhoisRecordsAssociatedWithName = type(
    "WhoisRecordsAssociatedWithName",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v0/whois/name",
        "query_parameters": ["name", "exact", "maxResults"],
    },
)

WhoisRecordsAssociatedWithNameServer = type(
    "WhoisRecordsAssociatedWithNameServer",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v0/whois/nameserver",
        "query_parameters": ["nameserver", "exact", "maxResults"],
    },
)

WhoisRecordsAssociatedWithOrganization = type(
    "WhoisRecordsAssociatedWithOrganization",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v0/whois/org",
        "query_parameters": ["org", "exact", "maxResults"],
    },
)

WhoisRecordsAssociatedWithPhoneNumber = type(
    "WhoisRecordsAssociatedWithPhoneNumber",
    (RiskIQAction,),
    {
        "verb": "get",
        "endpoint": base_url + "v0/whois/phone",
        "query_parameters": ["phone", "exact", "maxResults"],
    },
)
