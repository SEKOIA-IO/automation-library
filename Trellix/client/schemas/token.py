"""All models related to auth token workflow."""
from enum import Enum
from time import time
from typing import List, Set

from pydantic import BaseModel


class HttpToken(BaseModel):
    """Http model for auth token response."""

    tid: int
    token_type: str
    expires_in: int
    access_token: str


class Scope(str, Enum):
    """
    Scope enum.

    Some of them can be found here:
    https://docs.trellix.com/fr/bundle/mvision-endpoint-detection-and-response-product-guide/page/GUID-A5D15066-C579-459F-9686-D79AF40E66D7.html
    """

    SOC_HTS_C = "soc.hts.c"
    SOC_HTS_R = "soc.hts.r"
    SOC_RTS_C = "soc.rts.c"
    SOC_RTS_R = "soc.rts.r"
    SOC_QRY_PR = "soc.qry.pr"
    SOC_CFG_W = "soc.cfg.w"
    SOC_CFG_R = "soc.cfg.r"
    MI_USER_INVESTIGATE = "mi.user.investigate"

    @classmethod
    def full_set_for_edr(cls) -> Set["Scope"]:
        """
        Get complete list of scopes to work with Trellix EDR.

        Returns:
            set:
        """
        return {
            cls.SOC_HTS_C,
            cls.SOC_HTS_R,
            cls.SOC_RTS_C,
            cls.SOC_RTS_R,
            cls.SOC_QRY_PR,
            cls.SOC_CFG_W,
            cls.SOC_CFG_R,
        }

    @classmethod
    def set_for_historical_searches(cls) -> Set["Scope"]:
        """
        Get complete list of scopes to work with Trellix EDR.

        Returns:
            set:
        """
        return {
            cls.SOC_HTS_C,
            cls.SOC_HTS_R,
        }

    @classmethod
    def set_for_realtime_searches(cls) -> Set["Scope"]:
        """
        Get complete list of scopes to work with Trellix EDR.

        Returns:
            set:
        """
        return {
            cls.SOC_RTS_C,
            cls.SOC_RTS_R,
        }

    @classmethod
    def set_for_configuration(cls) -> Set["Scope"]:
        """
        Get complete list of scopes to work with Trellix EDR.

        Returns:
            set:
        """
        return {
            cls.SOC_CFG_W,
            cls.SOC_CFG_R,
        }

    @classmethod
    def set_for_investigations(cls) -> Set["Scope"]:
        """
        Get complete list of scopes to work with Trellix EDR.

        Returns:
            set:
        """
        return {
            cls.MI_USER_INVESTIGATE,
        }


class TrellixToken(BaseModel):
    """Model to work with auth token with additional info."""

    token: HttpToken

    scopes: Set[Scope]
    created_at: int

    def is_valid(self, scopes: List[Scope] | None = None) -> bool:
        """
        Check if token is not expired yet and valid for defined scopes.

        Returns:
            bool:
        """
        return self.is_expired() and self.is_valid_for_scopes(scopes or [])

    def is_valid_for_scope(self, scope: Scope) -> bool:
        """
        Check if token is valid for defined scope.

        Returns:
            bool:
        """
        return scope in self.scopes

    def is_valid_for_scopes(self, scopes: List[Scope]) -> bool:
        """
        Check if token is valid for defined scopes.

        Returns:
            bool:
        """
        if scopes:
            return scopes == list(self.scopes)

        return True

    def is_expired(self) -> bool:
        """
        Check if token is expired.

        Returns:
            bool:
        """
        return self.created_at + self.token.expires_in > (time() - 1)
