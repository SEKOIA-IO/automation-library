import requests
from sekoia_automation.action import Action


class GetPrivateDomainsAction(Action):
    """
    Action to get the list of private domains
    """

    url = "https://publicsuffix.org/list/public_suffix_list.dat"
    private_domains_delimiter = "// ===BEGIN PRIVATE DOMAINS==="

    def _download_domain_list(self) -> str:
        response = requests.get(self.url)
        response.raise_for_status()
        return response.text

    def _extract_private_domains(self, content: str) -> list[str]:
        private_part = content.split(self.private_domains_delimiter)[1]
        return [
            item.strip().replace("*.", "")
            for item in private_part.splitlines()
            if item.strip() and not item.startswith("//")
        ]

    def run(self, arguments: dict) -> dict:
        raw = self._download_domain_list()
        domains = self._extract_private_domains(raw)
        return self.json_result("domains", domains)
