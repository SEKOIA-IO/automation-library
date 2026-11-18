from sekoia_automation.account_validator import AccountValidator

from easyvista_modules.action_base import EasyVistaHttpMixin


class EasyVistaAccountValidator(EasyVistaHttpMixin, AccountValidator):
    def validate(self) -> bool:
        return self.get("/requests", params={"max_rows": 1, "fields": "rfc_number"}) is not None
