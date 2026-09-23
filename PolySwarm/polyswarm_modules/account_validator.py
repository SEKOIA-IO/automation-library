"""Validate the configured PolySwarm key when someone saves the configuration.

Without this, a wrong or expired key is discovered by the first playbook that
fails in production. Sekoia calls this at configuration time instead, which is
the pattern most of the modules in their library follow.
"""

from polyswarm_api import exceptions as ps_exceptions
from requests import RequestException
from sekoia_automation.account_validator import AccountValidator

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.client import build_client


class PolyswarmAccountValidator(AccountValidator):
    """Check that the configured key can actually talk to PolySwarm."""

    module: PolyswarmModule

    def validate(self) -> bool:
        try:
            account = build_client(self.module.configuration).account_whois()
        except ps_exceptions.UsageLimitsExceededException:
            self.error("The PolySwarm account is over its usage limit. The key itself is valid.")
            return False
        except (ps_exceptions.PolyswarmException, RequestException) as exception:
            # Never quote the client's own message: it renders the request,
            # which carries the key.
            self.error(f"PolySwarm rejected the configured API key ({type(exception).__name__}).")
            return False

        if account is None:
            self.error("PolySwarm returned no account for the configured API key.")
            return False

        return True
