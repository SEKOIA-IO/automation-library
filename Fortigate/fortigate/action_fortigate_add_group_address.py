import requests
from requests import Response
from sekoia_automation.action import Action


class FortigateAddGroupAddress(Action):
    """
    Action to Add a Group Address on a remote fortigate
    """

    def run(self, arguments: dict) -> list:
        """
        Modify the members of the address group on the firewall.
        Parameters
        ----------
        name : the group name (type string)
        member_list : the modified list of objects for the group (type [])

        Returns
        -------
        Http status code: 200 if ok, 4xx if an error occurs
        """
        name = arguments["name"]
        new_member_list = arguments["member"]

        for firewall in self.module.configuration["firewalls"]:
            self.base_ip: str = firewall.get("base_ip")
            self.base_port: str = firewall.get("base_port")
            self.api_key: str = firewall.get("api_key")
            self.vdom: str = firewall.get("vdom", "root")

            objects = [["name", name]]

            if self.if_exists("firewall/addrgrp/", objects):
                grp_addr = self.get_api("firewall/addrgrp/" + name)
                members = grp_addr.json()["results"][0]["member"]
                existing_members = []
                for member in members:
                    existing_members.append(member["name"])

                member_list = new_member_list + existing_members

                name = str(name)
                member = []
                for member_elem in member_list:
                    member.append({"name": member_elem})
                payload = {"json": {"member": member}}
                self.set_api("firewall/addrgrp/" + name + "/", payload)

            else:
                self.add_fw_address_group(name, new_member_list)

        return objects

    def add_api(self, url, data=None):
        try:
            response: Response = requests.post(
                "https://" + self.base_ip + ":" + self.base_port + "/api/v2/cmdb/" + url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                params={"vdom": self.vdom},
                json=data,
                verify=False,
                timeout=2,
            )
            return response

        except requests.exceptions.Timeout:
            self.log("Timeout session on a firewall", fw_ip=self.base_ip, level="error")
            return False

        except Exception:
            self.log(
                "Impossible to add IP to the firewall",
                level="error",
                fw_ip=self.base_ip,
                fw_port=self.base_port,
                data=data,
            )
            return False

    def get_api(self, url, data=None):
        try:
            response: Response = requests.get(
                "https://" + self.base_ip + ":" + self.base_port + "/api/v2/cmdb/" + url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                params={"vdom": self.vdom},
                json=data,
                verify=False,
                timeout=2,
            )
            return response

        except requests.exceptions.Timeout:
            self.log("Timeout session on a firewall", fw_ip=self.base_ip, level="error")
            return False

        except Exception:
            self.log(
                "Impossible to add IP to the firewall",
                level="error",
                fw_ip=self.base_ip,
                fw_port=self.base_port,
                data=data,
            )
            return False

    def set_api(self, url, data=None):
        try:
            response: Response = requests.put(
                "https://" + self.base_ip + ":" + self.base_port + "/api/v2/cmdb/" + url,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self.api_key}",
                },
                params={"vdom": self.vdom},
                json=data,
                verify=False,
                timeout=2,
            )
            return response

        except requests.exceptions.Timeout:
            self.log("Timeout session on a firewall", fw_ip=self.base_ip, level="error")
            return False

        except Exception:
            self.log(
                "Impossible to add IP to the firewall",
                level="error",
                fw_ip=self.base_ip,
                fw_port=self.base_port,
                data=data,
            )
            return False

    def if_exists(self, url, objects):
        """
        Test if the objects exist in the url.
        Parameters
        ----------
        url: the api url to test the objects (type string)
        objects: the list of objects you want to test (type [[]])
            ex:
                objects =  [['name','srv-A'],['subnet','10.1.1.1/32']]
                self.if_exists('cmdb/firewall/address/', objects)
        Returns
        -------
        Return True if all the objects exist, otherwise False.
        """
        try:
            response: Response = self.get_api(url)
            data = response.json()

            for result in data["results"]:
                identical = True
                for obj in objects:
                    req_res = result[obj[0]]
                    if isinstance(req_res, list):
                        if (req_res != []) and (obj[1] != req_res[0]["name"]):
                            identical = False
                            break
                    elif obj[1] != req_res:
                        identical = False
                        break
                if identical:
                    return True
            return False
        except Exception:
            return False

    def add_fw_address_group(self, name, member_list):
        """
        Create address group on the firewall.
        Parameters
        ----------
        name : the group name (type string)
        member_list : the list of existing objects to add to the group (type [])

        Returns
        -------
        Http status code: 200 if ok, 4xx if an error occurs
        """
        name = str(name)
        member = []
        for member_elem in member_list:
            member.append({"name": member_elem})
        payload = {"json": {"name": name, "member": member}}

        return self.add_api("firewall/addrgrp/", payload)

    def set_fw_address_group(self, name, new_member_list):
        """
        Modify the members of the address group on the firewall.
        Parameters
        ----------
        name : the group name (type string)
        member_list : the modified list of objects for the group (type [])
        Returns
        -------
        Http status code: 200 if ok, 4xx if an error occurs
        """
        objects = [["name", name]]
        if self.if_exists("firewall/addrgrp/", objects):
            grp_addr = self.get_api("firewall/addrgrp/" + name)
            members = grp_addr.json()["results"][0]["member"]
            existing_members = []
            for member in members:
                existing_members.append(member["name"])

            member_list = new_member_list + existing_members

            name = str(name)
            member = []
            for member_elem in member_list:
                member.append({"name": member_elem})
            payload = {"json": {"member": member}}
            return self.set_api("firewall/addrgrp/" + name + "/", payload)

        else:
            return self.add_fw_address_group(name, new_member_list)
