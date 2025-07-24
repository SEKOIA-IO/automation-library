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
