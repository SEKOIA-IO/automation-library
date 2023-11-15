from aiolimiter import AsyncLimiter
from pydantic import BaseModel, Field, HttpUrl


class SalesforceModuleConfig(BaseModel):
    """Configuration for SalesforceModule."""

    client_secret: str = Field(secret=True)
    client_id: str
    base_url: HttpUrl
    org_type: str = "production"

    @property
    def rate_limiter(self) -> AsyncLimiter:
        """
        Get rate limit.

        During client initialization we should limit amount of concurrent requests to salesforce platform:
        * 25 requests per 20 seconds if it is production org type
        * 5 requests per 20 seconds for the rest of org types

        Docs: https://developer.salesforce.com/docs/atlas.en-us.salesforce_app_limits_cheatsheet.meta/salesforce_app_limits_cheatsheet/salesforce_app_limits_platform_api.htm

        Returns:
            int:
        """
        match self.org_type:
            case "production":
                return AsyncLimiter(25, 20)

            case "sandbox":
                return AsyncLimiter(25, 20)

            case _:
                return AsyncLimiter(5, 20)
