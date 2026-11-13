from sekoia_automation.account_validator import AccountValidator

from easyvista_modules.action_base import EasyVistaHttpMixin


class EasyVistaAccountValidator(EasyVistaHttpMixin, AccountValidator):
    def validate(self) -> bool:
        response = self.request("GET", "/requests", check=False, params={"max_rows": 1, "fields": "rfc_number"})
        if response is not None and response.status_code == 403:
            # A REST API profile limited to assets (asset connector) cannot read requests
            return self.get("/assets", params={"max_rows": 1, "fields": "asset_id"}) is not None
        if response is None or not self._handle_response(response):
            return False
        return self.json_object(response, "/requests") is not None
