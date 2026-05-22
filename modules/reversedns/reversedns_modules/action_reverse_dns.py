import socket
from sekoia_automation.action import Action


class ReverseDnsAction(Action):
    def run(self, arguments: dict) -> dict:
        ip_address = arguments.get("ip_address")

        if not ip_address:
            self.error("Aucune adresse IP fournie dans les arguments.")
            return {"error": "Missing ip_address argument"}

        try:
            # socket.gethostbyaddr renvoie un tuple (hostname, aliaslist, ipaddrlist)
            hostname, aliases, _ = socket.gethostbyaddr(ip_address)

            self.log(f"Résolution réussie : {ip_address} -> {hostname}")
            return {"ip_address": ip_address, "hostname": hostname, "aliases": aliases}

        except socket.herror as e:
            self.log(f"Impossible de résoudre l'IP {ip_address} : {str(e)}")
            return {"ip_address": ip_address, "hostname": None, "error": str(e)}
        except Exception as e:
            self.error(
                f"Erreur inattendue lors de la résolution de {ip_address} : {str(e)}"
            )
            return {"ip_address": ip_address, "hostname": None, "error": str(e)}
