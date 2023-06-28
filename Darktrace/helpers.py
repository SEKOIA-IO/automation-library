import hmac
import hashlib
import requests
from urllib.parse import urlparse


def generate_darktrace_signature(public_key: str, private_key: str, query: str, now: str) -> str:
    maccer = hmac.new(
        private_key.encode("ASCII"), (query + "\n" + public_key + "\n" + now).encode("ASCII"), hashlib.sha1
    )
    sig = maccer.hexdigest()

    return sig


def extract_query(request: requests.models.PreparedRequest) -> str:
    parsed_url = urlparse(request.url)
    query = parsed_url.path + "?" + parsed_url.query

    return query
