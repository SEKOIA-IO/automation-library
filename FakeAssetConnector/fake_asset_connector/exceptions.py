class FakeAssetCredentialsError(Exception):
    """Base exception for credential validation errors."""

    pass

class FakeAssetCredentialsUnexpectedError(FakeAssetCredentialsError):
    pass