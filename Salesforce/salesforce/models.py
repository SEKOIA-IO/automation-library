from aiolimiter import AsyncLimiter
from pydantic import BaseModel, Field, HttpUrl


class SalesforceModuleConfig(BaseModel):
    """Configuration for SalesforceModule."""

    client_secret: str = Field(secret=True)
    client_id: str = Field(required=True, description="Salesforce client id")
    base_url: HttpUrl = Field(required=True, description="Salesforce auth url")
    org_type: str = Field(default="production", required=True, description="Salesforce org type")
    rate_limit: str | None = Field(
        description=(
            "Rate limit for requests to salesforce."
            "Value should have next format {max_rate}/{time_period}. For example: 3/60"
            "If value is empty, Sekoia will use default rate limits. More information you can find in docs:"
            "https://developer.salesforce.com/docs/atlas.en-us.salesforce_app_limits_cheatsheet.meta/salesforce_app_limits_cheatsheet/salesforce_app_limits_platform_api.htm"
        )
    )

    @property
    def rate_limiter(self) -> AsyncLimiter:
        """
        Get rate limit.

        During client initialization we should limit amount of concurrent requests to salesforce platform:
        * 25 requests per 20 seconds if it is production org type
        * 5 requests per 20 seconds for the rest of org types

        Docs: https://developer.salesforce.com/docs/atlas.en-us.salesforce_app_limits_cheatsheet.meta/salesforce_app_limits_cheatsheet/salesforce_app_limits_platform_api.htm

        Returns:
            AsyncLimiter:
        """
        if self.rate_limit is not None and "/" in self.rate_limit:
            max_rate = float(self.rate_limit.split("/")[0])
            time_period = float(self.rate_limit.split("/")[-1])

            return AsyncLimiter(max_rate, time_period)

        match self.org_type:
            case "production":
                return AsyncLimiter(25, 20)

            case "sandbox":
                return AsyncLimiter(25, 20)

            case _:
                return AsyncLimiter(5, 20)
