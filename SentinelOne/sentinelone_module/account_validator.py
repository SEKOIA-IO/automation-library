from sekoia_automation.account_validator import AccountValidator
from functools import cached_property
from sentinelone_module.client import SentinelOneClient
from sentinelone_module.base import SentinelOneModule


class SentinelOneAccountValidator(AccountValidator):
    """Validator for SentinelOne account credentials."""

    module: SentinelOneModule

    @cached_property
    def client(self) -> SentinelOneClient:
        """Get the SentinelOne HTTP client instance.

        Returns:
            Configured SentinelOneClient instance.
        """
        configuration = self.module.configuration
        return SentinelOneClient(
            hostname=configuration.hostname,
            api_token=configuration.api_token,
            rate_limit_per_second=10,
        )

    def validate(self):
        """Validate the account by making a test API call."""
        try:
            response = self.client.get("/web/api/v2.1/agents/count", params={})
            if "data" in response:
                return True
            if "error" in response:
                self.log(f"Account validation failed: {response['error']}")
                self.error(f"Account validation failed: {response['error']}")
            return False
        except Exception as e:
            self.log(f"Account validation failed: {e}")
            self.error(f"Account validation failed: {e}")
            return False
