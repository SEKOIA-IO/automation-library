from datetime import datetime

import whois
from sekoia_automation.action import Action


# Returns an item in a list at a given index
def list_tool(item, list, number):
    if isinstance(item, list):
        return str(item[number])
    else:
        return item


# converts inputs into a string w/o u' prepended
def my_converter(obj):
    if isinstance(obj, datetime):
        return obj.__str__()
    else:
        return obj


# Converts a list of time objects into human readable format
def time_list_tool(obj):
    if obj is not None and isinstance(obj, list):
        for string in obj:
            my_converter(string)
        return string
    else:
        return obj


class WhoisAction(Action):
    def run(self, arguments):
        whois_result = whois.whois(arguments["query"])
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
