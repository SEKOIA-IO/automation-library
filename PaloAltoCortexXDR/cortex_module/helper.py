def handle_fqdn(fqdn: str) -> str:
    base_fqdn = fqdn.rstrip("/")
    issue_search_path = "/public_api/v1/issue/search"

    if base_fqdn.startswith("https://"):
        if base_fqdn.endswith(issue_search_path):
            return base_fqdn
        return f"{base_fqdn}{issue_search_path}"

    if base_fqdn.startswith("api-"):
        return f"https://{base_fqdn}{issue_search_path}"

    return f"https://api-{base_fqdn}{issue_search_path}"


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
