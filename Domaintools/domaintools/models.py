#!/usr/bin/env python3
"""
DomainTools Iris Investigate API Client
A comprehensive Python client for DomainTools API with security and error handling

Security Features:
- Input sanitization and validation
- Protection against injection attacks
- Rate limiting to prevent API abuse
- Secure HMAC authentication
- Proper error handling without exposing sensitive data
- Request timeout protection
- Retry logic for transient failures
"""

import os
import datetime
import urllib.parse
import requests
import hmac
import hashlib
import json
import time
import ipaddress
import re
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Import for base action class
try:
    from sekoia_automation.action import Action
except ImportError:
    Action = None  # Allow models.py to be imported standalone


@dataclass
class DomainToolsConfig:
    """Configuration class for DomainTools API credentials and settings"""

    api_username: str
    api_key: str
    host: str = "https://api.domaintools.com/"
    timeout: int = 30
    max_retries: int = 3
    rate_limit_delay: float = 0.1


class DomainToolsError(Exception):
    """Custom exception for DomainTools API errors"""

    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class DomainToolsClient:
    """DomainTools Iris Investigate API Client"""

    def __init__(self, config: DomainToolsConfig):
        self.config = config
        self._validate_config()
        self._setup_session()

    def _validate_config(self) -> None:
        """Validate configuration parameters"""
        if not self.config.api_username:
            raise DomainToolsError("API username is required")
        if not self.config.api_key:
            raise DomainToolsError("API key is required")
        if not self.config.host.startswith(("http://", "https://")):
            raise DomainToolsError("Host must include protocol (http:// or https://)")

    def _setup_session(self) -> None:
        """Setup requests session with retry strategy"""
        self.session = requests.Session()

        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.session.headers.update(
            {"User-Agent": "DomainToolsClient/1.0", "Accept": "application/json", "Content-Type": "application/json"}
        )

    def _validate_domain(self, domain: str) -> str:
        """Validate domain format"""
        if not domain or not isinstance(domain, str):
            raise DomainToolsError("Domain must be a non-empty string")

        domain = domain.strip().lower()

        if not domain or "." not in domain:
            raise DomainToolsError(f"Invalid domain format: {domain}")

        if domain.startswith(("http://", "https://")):
            domain = domain.split("://", 1)[1].split("/")[0]

        return domain

    def _validate_ip(self, ip: str) -> str:
        """Validate IP address format"""
        try:
            ipaddress.ip_address(ip.strip())
            return ip.strip()
        except ValueError:
            raise DomainToolsError(f"Invalid IP address format: {ip}")

    def _validate_email(self, email: str) -> str:
        """
        Validate email format using RFC 5322 simplified regex

        This regex checks for:
        - Local part: alphanumeric, dots, hyphens, underscores, plus signs
        - @ symbol
        - Domain part: alphanumeric, dots, hyphens
        - TLD: at least 2 characters
        """
        if not email or not isinstance(email, str):
            raise DomainToolsError("Email must be a non-empty string")

        email = email.strip().lower()

        # RFC 5322 simplified email regex
        email_pattern = re.compile(r"^[a-z0-9][a-z0-9._+-]*@[a-z0-9][a-z0-9.-]*\.[a-z]{2,}$", re.IGNORECASE)

        if not email_pattern.match(email):
            raise DomainToolsError(f"Invalid email format: {email}")

        return email

    def _sign_request(self, uri: str, timestamp: str) -> str:
        """Generate HMAC signature for API request"""
        params = "".join([self.config.api_username, timestamp, uri])
        return hmac.new(self.config.api_key.encode("utf-8"), params.encode("utf-8"), hashlib.sha1).hexdigest()

    def _make_request(self, uri: str, params: Optional[Dict] = None) -> Dict:
        """Make authenticated API request with iterative retry logic"""
        max_429_retries = 3  # Maximum number of 429 retries to prevent infinite loops

        for retry_count in range(max_429_retries + 1):
            try:
                # Rate limiting
                time.sleep(self.config.rate_limit_delay)

                # Generate authentication parameters
                timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                signature = self._sign_request(uri, timestamp)

                # Build request parameters
                request_params = {
                    "api_username": self.config.api_username,
                    "signature": signature,
                    "timestamp": timestamp,
                }
                if params:
                    request_params.update(params)

                # Make the request
                url = urllib.parse.urljoin(self.config.host, uri)
                response = self.session.get(url, params=request_params, timeout=self.config.timeout)

                # Handle rate limiting with iterative retry
                if response.status_code == 429:
                    if retry_count < max_429_retries:
                        retry_after = int(response.headers.get("Retry-After", 60))
                        logger.warning(
                            f"Rate limited (429), retrying after {retry_after}s (attempt {retry_count + 1}/{max_429_retries})"
                        )
                        time.sleep(retry_after)
                        continue  # Retry the request
                    else:
                        raise DomainToolsError(f"Rate limit exceeded after {max_429_retries} retries", status_code=429)

                # Check for errors
                if not response.ok:
                    raise DomainToolsError(
                        f"API request failed with status {response.status_code}", status_code=response.status_code
                    )

                return response.json()

            except requests.exceptions.Timeout as e:
                logger.error(f"Request timeout for {uri}: {e}")
                raise DomainToolsError(f"Request timeout: {e}")
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Connection error for {uri}: {e}")
                raise DomainToolsError(f"Connection error: {e}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Request error for {uri}: {e}")
                raise DomainToolsError(f"Request error: {e}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON response from {uri}: {e}")
                raise DomainToolsError(f"Invalid JSON response: {e}")

        # This should never be reached, but included for completeness
        raise DomainToolsError("Request failed after all retry attempts")

    def domain_reputation(self, domain: str) -> Dict:
        """
        Get domain reputation/risk score using Iris Investigate

        Args:
            domain: Domain name to analyze

        Returns:
            Domain reputation and risk data
        """
        logger.info(f"Getting domain reputation for: {domain}")
        domain = self._validate_domain(domain)

        # Use Iris Investigate endpoint with domain search
        uri = "/v1/iris-investigate/"
        params = {"domain": domain}

        result = self._make_request(uri, params)
        logger.info(f"Successfully retrieved reputation for {domain}")
        return result

    def pivot_action(self, search_term: str, search_type: str, limit: int = 100) -> Dict:
        """
        Find domains connected by any supported Iris Investigate search parameter

        Args:
            search_term: Search term (domain, IP, email, etc.)
            search_type: Type of pivot ('domain', 'ip', 'email', 'nameserver_host', etc.)
            limit: Maximum number of results to return (100-10000)

        Returns:
            Connected domains data
        """
        logger.info(f"Performing pivot action: {search_type} -> {search_term}")

        if not search_term:
            raise DomainToolsError("Search term cannot be empty")

        # Validate search term based on type
        if search_type == "domain":
            search_term = self._validate_domain(search_term)
        elif search_type == "ip":
            search_term = self._validate_ip(search_term)
        elif search_type == "email":
            search_term = self._validate_email(search_term)

        uri = "/v1/iris-investigate/"
        # Use the search_type as the parameter name
        params = {search_type: search_term, "limit": max(100, min(limit, 10000))}  # Ensure between 100-10000

        result = self._make_request(uri, params)
        logger.info(f"Successfully performed pivot action for {search_term}")
        return result

    def reverse_domain(self, domain: str) -> Dict:
        """
        Get hosting history for a domain

        Args:
            domain: Domain name to analyze

        Returns:
            Domain IP and infrastructure data
        """
        logger.info(f"Getting reverse domain data for: {domain}")
        domain = self._validate_domain(domain)

        # Use the correct hosting history endpoint
        uri = f"/v1/{domain}/hosting-history/"

        result = self._make_request(uri)
        logger.info(f"Successfully retrieved reverse domain data for {domain}")
        return result

    def reverse_ip(self, ip: str) -> Dict[str, Any]:
        """
        Query DomainTools Reverse IP API to find domains hosted on the same IP.

        Args:
            ip: The IP address to look up

        Returns:
            Dictionary containing the API response with domain list

        Example:
            results = client.reverse_ip('8.8.8.8')
            print(f"Found {results['response']['ip_addresses']['domain_count']} domains")
        """
        logger.info(f"Getting reverse IP data for: {ip}")
        ip = self._validate_ip(ip)

        uri = f"/v1/{ip}/reverse-ip/"

        result = self._make_request(uri)
        logger.info(f"Successfully retrieved reverse IP data for {ip}")
        return result

    def reverse_email(self, email: str, limit: int = 100) -> Dict:
        """
        Find domains associated with an email address

        Args:
            email: Email address to search
            limit: Maximum number of results to return (100-10000)

        Returns:
            Domains associated with the email
        """
        logger.info(f"Getting reverse email data for: {email}")
        email = self._validate_email(email)

        # Use Iris Investigate with email parameter
        uri = "/v1/iris-investigate/"
        params = {"email": email, "limit": max(100, min(limit, 10000))}  # Ensure minimum 100

        result = self._make_request(uri, params)
        logger.info(f"Successfully retrieved reverse email data for {email}")
        return result

    def lookup_domain(self, domain: str) -> Dict:
        """
        Get all Iris Investigate data for a domain

        Args:
            domain: Domain name to lookup

        Returns:
            Complete domain investigation data
        """
        logger.info(f"Performing complete domain lookup for: {domain}")
        domain = self._validate_domain(domain)

        uri = "/v1/iris-investigate/"
        params = {"domain": domain}  # Changed from 'q' to 'domain'

        result = self._make_request(uri, params)
        logger.info(f"Successfully retrieved complete domain data for {domain}")
        return result


class BaseDomaintoolsAction:
    """Base class for all DomainTools actions to avoid code duplication

    Subclasses must define the 'action_name' class attribute with the appropriate
    action identifier (e.g., 'domain_reputation', 'lookup_domain', etc.)
    """

    action_name: Optional[str] = None
    module: Any  # Will be set by sekoia_automation framework

    def run(self, arguments: dict[str, Any]) -> dict[str, Any]:
        if self.action_name is None:
            raise NotImplementedError("Subclass must define 'action_name' class attribute")

        try:
            config = DomainToolsConfig(
                api_username=self.module.configuration["api_username"],
                api_key=self.module.configuration["api_key"],
                host="https://api.domaintools.com/",
            )

            parsed_args: dict[str, Any] = {
                "domain": arguments.get("domain"),
                "ip": arguments.get("ip"),
                "email": arguments.get("email"),
                "query_value": arguments.get("query_value"),
                "pivot_type": arguments.get("pivot_type"),
                "domaintools_action": self.action_name,
            }

            response = DomaintoolsrunAction(config, parsed_args)
            return response

        except DomainToolsError as e:
            error_msg = {"error": f"DomainTools client initialization error: {e}"}
            logger.error(json.dumps(error_msg, indent=2))
            return error_msg
        except Exception as e:
            error_msg = {"error": f"Unexpected initialization error: {e}"}
            logger.error(json.dumps(error_msg, indent=2))
            return error_msg


def DomaintoolsrunAction(config: DomainToolsConfig, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a specific DomainTools action"""
    try:

        client = DomainToolsClient(config)

        arg_domain = arguments.get("domain")
        arg_ip = arguments.get("ip")
        arg_email = arguments.get("email")
        arg_query_value = arguments.get("query_value")
        arg_pivot_type = arguments.get("pivot_type")
        arg_action = arguments.get("domaintools_action")

        dispatch = {
            "domain_reputation": ("domain_reputation", lambda: [arg_domain], {}, "Domain Reputation"),
            "pivot_action": ("pivot_action", lambda: [arg_query_value, arg_pivot_type], {"limit": 100}, "Pivot Action"),
            "reverse_domain": ("reverse_domain", lambda: [arg_domain], {}, "Reverse Domain"),
            "reverse_ip": ("reverse_ip", lambda: [arg_ip], {}, "Reverse IP"),
            "reverse_email": ("reverse_email", lambda: [arg_email], {"limit": 100}, "Reverse Email"),
            "lookup_domain": ("lookup_domain", lambda: [arg_domain], {}, "Lookup Domain"),
        }

        def call_method(method_name, args, kwargs):
            try:
                method = getattr(client, method_name)
            except AttributeError:
                return False, f"Client has no method '{method_name}'"

            try:
                result = method(*args, **kwargs)
                return True, result
            except DomainToolsError as e:
                return False, f"DomainToolsError: {e}"
            except Exception as e:
                return False, f"Unexpected error: {e}"

        if arg_action:
            if arg_action not in dispatch:
                return {"error": f"Unknown action '{arg_action}'."}

            method_name, args_fn, kwargs, label = dispatch[arg_action]
            args = args_fn()
            ok, payload = call_method(method_name, args, kwargs)

            if ok:
                # Payload returned by the client method
                # It may be:
                #  - a dict with a 'response' key -> return that
                #  - a dict with an 'error' key -> return top-level error
                #  - some other dict / value -> return it directly or wrap as error if None
                try:
                    # If payload is a dict, check common shapes
                    if isinstance(payload, dict):
                        # If the client already wrapped an error, preserve it as top-level "error"
                        if "error" in payload:
                            # payload["error"] may be string or dict; normalize
                            return {"error": payload["error"]}
                        # If there is a nested 'response' key, return it (most normal case)
                        if "response" in payload:
                            return payload["response"]
                        # Some endpoints return the full response at top-level (no 'response' key)
                        # return the payload as-is
                        return payload
                    else:
                        # Non-dict payload (string, list, None, etc.)
                        if payload is None:
                            return {"error": f"No response returned for action {label}."}
                        # For strings (e.g. error messages returned by call_method on exceptions), wrap in error
                        if isinstance(payload, str):
                            # If payload already looks like 'DomainToolsError: ...' or similar, preserve it
                            return {"error": payload}
                        # otherwise serialize the payload
                        return payload
                except Exception as e:
                    return {"error": f"Failed to extract response: {e}"}
            else:
                # call_method already returned False; payload may be an error string or exception info
                return {"error": payload}

        # If no action specified, return error
        return {"error": "No action specified in arguments"}

    except DomainToolsError as e:
        return {"error": f"DomainTools client initialization error: {e}"}
    except Exception as e:
        return {"error": f"Unexpected initialization error: {e}"}
