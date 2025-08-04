def handle_fqdn(fqdn: str) -> str:
    base_fqdn = fqdn.rstrip("/")

    if base_fqdn.startswith("https://"):
        if base_fqdn.endswith("/public_api/v1/alerts/get_alerts_multi_events"):
            return base_fqdn
        return f"{base_fqdn}/public_api/v1/alerts/get_alerts_multi_events"

    if base_fqdn.startswith("api-"):
        return f"https://{base_fqdn}/public_api/v1/alerts/get_alerts_multi_events"

    return f"https://api-{base_fqdn}/public_api/v1/alerts/get_alerts_multi_events"


def format_fqdn(fqdn: str) -> str:
    """
    Format the FQDN to a valid URL.

    Args:
        fqdn: str

    Returns:
        str:
    """
    if fqdn.startswith("https://"):
        return fqdn

    if fqdn.startswith("api-"):
        return f"https://{fqdn}"

    return f"https://api-{fqdn}"
