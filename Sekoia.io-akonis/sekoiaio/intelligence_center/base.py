from posixpath import join as urljoin

from sekoia_automation.action import Action


class InThreatBaseAction(Action):
    @property
    def headers(self) -> dict:
        api_key = self.module.configuration["api_key"]
        return {"Authorization": f"Bearer {api_key}"}

    def url(self, path: str) -> str:
        return urljoin(self.module.configuration["base_url"], "api/v2/inthreat", path)

    def run(self, arguments: dict) -> dict:
        """Method that each action should implement to contain its logic.

        Should return its results as a JSON serializable dict."""
        raise NotImplementedError
