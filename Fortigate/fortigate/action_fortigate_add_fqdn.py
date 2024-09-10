import json

import requests
from requests import Response
from sekoia_automation.action import Action


class FortigateAddFQDNAction(Action):
    """
    Action to Add an IP Address on a remote fortigate
    """

    def run(self, arguments: dict) -> dict:
        """
        Parameters
        ----------
        name: the fw address object name (type string)
        fqdn: the fqdn to be blocked, (for ex: 'example.domain.com') (type string)
        associated_interface: interface of the object, leave blank for 'Any' (default: Any) (type string)
        comment: (default none) (type string)

        Returns
        -------
        Http status code: 200 if ok, 4xx if an error occurs
        """
        name = arguments["name"]
        fqdn = arguments["fqdn"]
        associated_interface = arguments.get("associated_interface", "")
        comment = arguments.get("comment", "")

        payload: dict = {
            "json": {
                "type": "fqdn",
                "name": name,
                "fqdn": fqdn,
                "associated-interface": associated_interface,
                "comment": comment,
            }
        }

        for firewall in self.module.configuration["firewalls"]:
            base_ip: str = firewall.get("base_ip")
            base_port: str = firewall.get("base_port")
            api_key: str = firewall.get("api_key")
            vdom: str = firewall.get("vdom", "root")

            try:
                response: Response = requests.post(
                    "https://" + base_ip + ":" + base_port + "/api/v2/cmdb/firewall/address/",
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {api_key}",
                    },
                    params={"vdom": vdom},
                    data=json.dumps(payload),
                    verify=False,
                    timeout=10,
                )
                response.raise_for_status()

            except requests.exceptions.Timeout:
                self.log("Timeout session on a firewall", fw_ip=base_ip, level="error")

            except Exception:
                self.log(
                    "Impossible to add IP to the firewall",
                    level="error",
                    fw_ip=base_ip,
                    fw_port=base_port,
                    data=payload,
                )

        return payload
