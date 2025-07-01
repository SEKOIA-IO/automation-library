def handle_uri(uri: str) -> str:
    """
    Handle the URI for the asset connector.

    Args:
        uri (str): The URI to handle.

    Returns:
        str: The handled URI.
    """
    uri = uri.rstrip("/")

    if uri.startswith("http://"):
        uri = uri.replace("http://", "https://", 1)

    if not uri.startswith("https://"):
        uri = f"https://{uri}"

    return uri


def map_os_type(os_type: str | None) -> int | None:
    os_types = {
        "Windows": 100,
        "Windows Mobile": 101,
        "Linux": 200,
        "Android": 201,
        "macOS": 300,
        "iOS": 301,
        "iPadOS": 302,
        "Solaris": 400,
        "AIX": 401,
        "HP-UX": 402,
    }
    if os_type is None:
        return None
    return os_types.get(os_type, 99)
