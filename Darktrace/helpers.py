import hashlib
import hmac
from urllib.parse import urlparse

import requests


def generate_darktrace_signature(public_key: str, private_key: str, query: str, now: str) -> str:
    maccer = hmac.new(
        private_key.encode("ASCII"), (query + "\n" + public_key + "\n" + now).encode("ASCII"), hashlib.sha1
    )
    sig = maccer.hexdigest()

    return sig


def extract_query(request: requests.models.PreparedRequest) -> str:
    parsed_url = urlparse(request.url)
    query = str(parsed_url.path) + "?" + str(parsed_url.query)

    return query
