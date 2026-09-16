import ipaddress
from datetime import datetime

import whois
from sekoia_automation.action import Action
from tldextract import extract

try:
    from whois.parser import PywhoisError as WhoisLookupError
except ImportError:
    try:
        from whois import WhoisError as WhoisLookupError
    except ImportError:
        WhoisLookupError = Exception


# Returns an item in a list at a given index
def list_tool(item, item_type, number):
    if isinstance(item, item_type):
        return str(item[number])
    else:
        return item


# converts inputs into a string w/o u' prepended
def my_converter(obj):
    if isinstance(obj, datetime):
        if obj.tzinfo is not None:
            obj = obj.replace(tzinfo=None)
        return obj.__str__()
    else:
        return obj


# Converts a list of time objects into human readable format
def time_list_tool(obj):
    if obj is not None and isinstance(obj, list):
        return my_converter(obj[-1]) if obj else obj
    return my_converter(obj)


# Checks if the input is an IP address
def is_ip_adress(ip_adresse: str) -> bool:
    try:
        ipaddress.ip_address(ip_adresse)
        return True
    except ValueError:
        return False


# Extracts the domain and suffix from a URL
def extract_domain_from_url(arg: str) -> str:

    if is_ip_adress(arg):
        return arg

    extract_domain = extract(arg)
    return f"{extract_domain.domain}.{extract_domain.suffix}"


class WhoisAction(Action):
    def run(self, arguments):
        try:
            get_domain = extract_domain_from_url(arguments["query"])
            whois_result = whois.whois(get_domain)
            return {
                "Domain": {
                    "Name": str(list_tool(whois_result.domain_name, list, 0)),
                    "Whois": {
                        "Domain": str(list_tool(whois_result.domain_name, list, 0)),
                        "DomainStatus": whois_result.status,
                        "DNSSec": str(whois_result.dnssec),
                        "Raw": str(whois_result.text),
                        "NameServers": whois_result.name_servers,
                        "CreationDate": str(time_list_tool(whois_result.creation_date)),
                        "UpdatedDate": str(time_list_tool(whois_result.updated_date)),
                        "ExpirationDate": str(time_list_tool(whois_result.expiration_date)),
                        "Registrar": {
                            "Name": str(whois_result.registrar),
                            "AbuseEmail": str(list_tool(whois_result.emails, list, 0)),
                        },
                        "Registrant": {
                            "Name": str(whois_result.get("name")),
                            "Email": str(list_tool(whois_result.emails, list, 1)),
                        },
                    },
                }
            }
        except WhoisLookupError:
            return {}
