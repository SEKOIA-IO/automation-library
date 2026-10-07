class AnozrwayError(Exception):
    """Base exception for Anozrway client errors"""


class AnozrwayAuthError(AnozrwayError):
    """Authentication/authorization errors"""


class AnozrwayRateLimitError(AnozrwayError):
    """Rate limit exceeded errors"""
