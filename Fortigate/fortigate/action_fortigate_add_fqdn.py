import json
from typing import Annotated

import requests
from pydantic import BaseModel, Field, StringConstraints
from requests import Response
from sekoia_automation.action import Action

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class FortigateAddFQDNArguments(BaseModel):
    name: NonEmptyStr = Field(..., description="the fw address object name")
    fqdn: NonEmptyStr = Field(..., description="the fqdn to be blocked, (for ex: 'example.domain.com')")
    associated_interface: str = Field(default="", description="interface of the object, leave blank for 'Any'")
    comment: str = Field(default="", description="comment")


class FortigateAddFQDNAction(Action):
    """
    Action to Add an IP Address on a remote fortigate
    """

    def run(self, arguments: FortigateAddFQDNArguments) -> dict | None:
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
        name = arguments.name
        fqdn = arguments.fqdn
        associated_interface = arguments.associated_interface
        comment = arguments.comment

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
