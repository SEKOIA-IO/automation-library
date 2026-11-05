import re

import tldextract

HOSTNAME_REGEX = re.compile(rb"[a-z0-9-_.]+")
LETTER_REGEX = re.compile(rb"[a-z]")

# Bundled public suffix list only: nothing is fetched at runtime
_extract = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None, fallback_to_snapshot=True)


# Copy of HolmSecurity holm_security/asset_connector/hostname.py (itself a copy of
# sekoia_automation_models.hostname.split_hostname): import it from there once models 1.5.0 is released
def split_hostname(value: str | None) -> tuple[str | None, str | None]:
    """
    Split a name into the `(hostname, domain)` pair the asset management API accepts.

    A fully qualified name is split on its first label. Returns `(None, None)` when no
    usable hostname can be derived.
    """
    if not value:
        return None, None

    name = value.strip().lower()
    domain = None
    if "." in name and _extract(name).suffix:
        name, _, domain = name.partition(".")

    try:
        # The idna codec also rejects empty labels and labels over 63 characters
        encoded = name.encode("idna")
    except UnicodeError:
        return None, None

    if not HOSTNAME_REGEX.fullmatch(encoded) or not LETTER_REGEX.search(encoded):
        return None, None

    return name, domain or None
