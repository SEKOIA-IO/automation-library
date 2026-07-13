import json
from typing import Annotated

import requests
from pydantic import BaseModel, Field, IPvAnyAddress, StringConstraints
from requests import Response
from sekoia_automation.action import Action

NonEmptyStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class FortigateAddIPArguments(BaseModel):
    name: NonEmptyStr = Field(..., description="the fw address object name")
    ip: IPvAnyAddress = Field(..., description="the ip address to be blocked, (for ex: '1.1.1.1')")
    associated_interface: str = Field(default="", description="interface of the object, leave blank for 'Any'")
    comment: str = Field(default="", description="comment")


class FortigateAddIPAction(Action):
    """
    Action to Add an IP Address on a remote fortigate
    """

    def run(self, arguments: FortigateAddIPArguments) -> dict | None:
        """
        Parameters
        ----------
        name: the fw address object name (type string)
        ip: the ip address to be blocked, (for ex: '1.1.1.1') (type string)
        associated_interface: interface of the object, leave blank for 'Any' (default: Any) (type string)
        comment: (default none) (type string)

        Returns
        -------
        Http status code: 200 if ok, 4xx if an error occurs
        """

        ip = str(arguments.ip)
        name = arguments.name
        associated_interface = arguments.associated_interface
        comment = arguments.comment

        payload: dict = {
            "json": {
                "type": "ipmask",
                "name": name,
                "subnet": ip + "/32",
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
                self.log("Time out session on a firewall", fw_ip=base_ip, level="error")

            except Exception:
                self.log(
                    "Impossible to add IP to the firewall",
                    level="error",
                    fw_ip=base_ip,
                    fw_port=base_port,
                    data=payload,
                )
                pass

        return payload
