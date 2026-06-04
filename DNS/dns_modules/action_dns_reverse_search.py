import socket
from sekoia_automation.action import Action

class DnsReverseSearchAction(Action):
    def run(self, arguments: dict) -> dict:
        ip_address = arguments.get("ip_address")

        if not ip_address:
            self.error("No IP address provided in arguments.")
            return {"error": "Missing ip_address argument"}

        try:
            hostname, aliases, _ = socket.gethostbyaddr(ip_address)
            self.log(f"Successfully resolved: {ip_address} -> {hostname}", level="info")
            return {
                "ip_address": ip_address,
                "hostname": hostname,
                "aliases": aliases,
                "error": None
            }

        except socket.herror as e:
            self.log(f"Unable to resolve IP {ip_address}: {str(e)}", level="warning")
            return {
                "ip_address": ip_address,
                "hostname": None,
                "aliases": [],
                "error": str(e)
            }
        except Exception as e:
            error_class = e.__class__.__name__
            self.error(f"Unexpected error [{error_class}] during resolution of {ip_address}: {str(e)}")
            return {
                "ip_address": ip_address,
                "hostname": None,
                "aliases": [],
                "error": f"[{error_class}] {str(e)}"
            }
