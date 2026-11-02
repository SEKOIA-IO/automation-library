from sekoia_automation.account_validator import AccountValidator

from easyvista.action_base import EasyVistaHttpMixin


class EasyVistaAccountValidator(EasyVistaHttpMixin, AccountValidator):
    def validate(self) -> bool:
        return self.request("GET", "/requests", params={"max_rows": 1, "fields": "rfc_number"}) is not None
