"""Validate the configured PolySwarm key when someone saves the configuration.

Without this, a wrong or expired key is discovered by the first playbook that
fails in production. Sekoia calls this at configuration time instead, which is
the pattern most of the modules in their library follow.

Each failure is told apart by what it proves. A 401 or 403 proves the key is
wrong. A spent quota proves the opposite, because PolySwarm only counts the
calls of a key it has accepted. Anything else, such as a timeout or a gateway
error, proves nothing about the key, and saying the key was rejected would send
the person to the wrong place.
"""

from polyswarm_api import exceptions as ps_exceptions
from sekoia_automation.account_validator import AccountValidator

from polyswarm_modules import PolyswarmModule
from polyswarm_modules.client import CLIENT_ERRORS, MISSING_RESULT, build_client, failure_kind, status_of

# Which statuses mean a rejected key is this check's own decision; the lookup
# is client.status_of and the display text is client.failure_kind.
REJECTED_STATUSES: frozenset[int] = frozenset({401, 403})


class PolyswarmAccountValidator(AccountValidator):
    """Check that the configured key can actually talk to PolySwarm."""

    module: PolyswarmModule

    def validate(self) -> bool:
        try:
            account = build_client(self.module.configuration).account_whois()
        except ps_exceptions.UsageLimitsExceededException:
            # The quota is only counted for a key PolySwarm has accepted, so this
            # is not a reason to refuse the configuration. Failing here would
            # stop someone saving a working key on the day they most need it.
            self.log(
                "The PolySwarm account is over its usage limit. The key itself was accepted.",
                level="warning",
            )
            return True
        except MISSING_RESULT:
            return self._refuse("PolySwarm returned no account for the configured API key.")
        except CLIENT_ERRORS as exception:
            # Never quote the client's own message: it renders the request,
            # which carries the key.
            if status_of(exception) in REJECTED_STATUSES:
                return self._refuse(f"PolySwarm rejected the configured API key ({failure_kind(exception)}).")
            return self._refuse(
                f"PolySwarm could not be reached to check the configured API key ({failure_kind(exception)}). "
                "The key has not been rejected, try again."
            )

        if account is None:
            return self._refuse("PolySwarm returned no account for the configured API key.")

        return True

    def _refuse(self, message: str) -> bool:
        """Record a failed validation where the person saving it and the run log can both see it."""
        self.log(message, level="error")
        self.error(message)
        return False
