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
from typing import Dict, List, Optional, Union, Any
from dataclasses import dataclass
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


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
        if not self.config.host.startswith(('http://', 'https://')):
            raise DomainToolsError("Host must include protocol (http:// or https://)")
            
    def _setup_session(self) -> None:
        """Setup requests session with retry strategy"""
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=self.config.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.headers.update({
            'User-Agent': 'DomainToolsClient/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def _validate_domain(self, domain: str) -> str:
        """Validate domain format"""
        if not domain or not isinstance(domain, str):
            raise DomainToolsError("Domain must be a non-empty string")
            
        domain = domain.strip().lower()
        
        if not domain or '.' not in domain:
            raise DomainToolsError(f"Invalid domain format: {domain}")
            
        if domain.startswith(('http://', 'https://')):
            domain = domain.split('://', 1)[1].split('/')[0]
            
        return domain
    
    def _validate_ip(self, ip: str) -> str:
        """Validate IP address format"""
        try:
            ipaddress.ip_address(ip.strip())
            return ip.strip()
        except ValueError:
            raise DomainToolsError(f"Invalid IP address format: {ip}")
    
    def _validate_email(self, email: str) -> str:
        """Basic email validation"""
        if not email or '@' not in email or '.' not in email.split('@')[1]:
            raise DomainToolsError(f"Invalid email format: {email}")
        return email.strip().lower()
    
    def _sign_request(self, uri: str, timestamp: str) -> str:
        """Generate HMAC signature for API request"""
        params = "".join([self.config.api_username, timestamp, uri])
        return hmac.new(
            self.config.api_key.encode("utf-8"),
            params.encode("utf-8"),
            hashlib.sha1
        ).hexdigest()
    
    def _make_request(self, uri: str, params: Optional[Dict] = None) -> Dict:
        """Make authenticated API request"""
        try:
            time.sleep(self.config.rate_limit_delay)
            
            timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            signature = self._sign_request(uri, timestamp)
            
            request_params = {
                "api_username": self.config.api_username,
                "signature": signature,
                "timestamp": timestamp,
            }
            
            if params:
                request_params.update(params)
            
            url = urllib.parse.urljoin(self.config.host, uri)
            logger.debug(f"Making request to: {url}")
            logger.debug(f"Request params: {request_params}")
            
            response = self.session.get(
                url,
                params=request_params,
                timeout=self.config.timeout
            )
            
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                logger.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return self._make_request(uri, params)
            
            if not response.ok:
                error_msg = f"API request failed with status {response.status_code}"
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        error_msg += f": {error_data['error'].get('message', error_data['error'])}"
                except:
                    error_msg += f": {response.text}"
                
                raise DomainToolsError(
                    error_msg,
                    status_code=response.status_code,
                    response_data=error_data if 'error_data' in locals() else None
                )
            
            return response.json()
            
        except requests.RequestException as e:
            raise DomainToolsError(f"Network error: {str(e)}")
        except json.JSONDecodeError as e:
            raise DomainToolsError(f"Invalid JSON response: {str(e)}")
    
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
        params = {
            'domain': domain
        }
        
        result = self._make_request(uri, params)
        logger.info(f"Successfully retrieved reputation for {domain}")
        return result
    
    def lookup_domain_risk(self, domain: str) -> Dict:
        """
        Get domain risk score - alias for domain_reputation
        
        Args:
            domain: Domain name to analyze
            
        Returns:
            Domain risk data
        """
        return self.domain_reputation(domain)
    
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
        if search_type == 'domain':
            search_term = self._validate_domain(search_term)
        elif search_type == 'ip':
            search_term = self._validate_ip(search_term)
        elif search_type == 'email':
            search_term = self._validate_email(search_term)
        
        uri = "/v1/iris-investigate/"
        # Use the search_type as the parameter name
        params = {
            search_type: search_term,
            'limit': max(100, min(limit, 10000))  # Ensure between 100-10000
        }
        
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
    
    def reverse_ip(self, ip: str, limit: int = 100) -> Dict:
        """
        Find domains hosted on an IP address using Iris Investigate
        
        Args:
            ip: IP address to search
            limit: Maximum number of results to return (100-10000)
            
        Returns:
            Domains hosted on the IP
        """
        logger.info(f"Getting reverse IP data for: {ip}")
        ip = self._validate_ip(ip)
        
        # Use Iris Investigate with ip parameter
        uri = "/v1/iris-investigate/"
        params = {
            'ip': ip,
            'limit': max(100, min(limit, 10000))
        }
        
        result = self._make_request(uri, params)
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
        params = {
            'email': email,
            'limit': max(100, min(limit, 10000))  # Ensure minimum 100
        }
        
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
        params = {'domain': domain}  # Changed from 'q' to 'domain'
        
        result = self._make_request(uri, params)
        logger.info(f"Successfully retrieved complete domain data for {domain}")
        return result
    
    def get_domain_profile(self, domain: str) -> Dict:
        """
        Get comprehensive domain profile data
        
        Args:
            domain: Domain name to profile
            
        Returns:
            Domain profile data
        """
        logger.info(f"Getting domain profile for: {domain}")
        domain = self._validate_domain(domain)
        
        uri = f"/v1/{domain}/"
        
        result = self._make_request(uri)
        logger.info(f"Successfully retrieved domain profile for {domain}")
        return result
    
    def get_whois_data(self, domain: str) -> Dict:
        """
        Get parsed WHOIS data for a domain
        
        Args:
            domain: Domain name to query
            
        Returns:
            WHOIS data
        """
        logger.info(f"Getting WHOIS data for: {domain}")
        domain = self._validate_domain(domain)
        
        uri = f"/v1/{domain}/whois/parsed/"
        
        result = self._make_request(uri)
        logger.info(f"Successfully retrieved WHOIS data for {domain}")
        return result


def create_client_from_env() -> DomainToolsClient:
    """
    Create DomainTools client from environment variables
    
    Environment variables:
        DOMAINTOOLS_API_USERNAME: API username
        DOMAINTOOLS_API_KEY: API key
        DOMAINTOOLS_HOST: API host (optional, defaults to https://api.domaintools.com/)
    
    Returns:
        Configured DomainToolsClient instance
        
    Raises:
        DomainToolsError: If required environment variables are missing
    """
    api_username = os.getenv('DOMAINTOOLS_API_USERNAME')
    api_key = os.getenv('DOMAINTOOLS_API_KEY')
    host = os.getenv('DOMAINTOOLS_HOST', 'https://api.domaintools.com/')
    
    if not api_username:
        raise DomainToolsError("DOMAINTOOLS_API_USERNAME environment variable is required")
    if not api_key:
        raise DomainToolsError("DOMAINTOOLS_API_KEY environment variable is required")
    
    config = DomainToolsConfig(
        api_username=api_username,
        api_key=api_key,
        host=host
    )
    
    return DomainToolsClient(config)


def DomaintoolsrunAction(config: DomainToolsConfig, arguments: dict[str, Any]) -> str:
    """Execute a specific DomainTools action"""
    try:
        
        client = DomainToolsClient(config)
        
        #arg_domain = "google.com"
        #arg_ip = "1.1.1.1"
        #arg_email = "admin@google.com"
        arg_domain = arguments.get("domain")
        arg_ip = arguments.get("ip")
        arg_email = arguments.get("email")
        # Name of the client method to call, see below
        arg_action = arguments.get("domaintools_action")
        
        dispatch = {
            "domain_reputation": ("domain_reputation", lambda: [arg_domain], {}, "Domain Reputation"),
            "pivot_action": ("pivot_action", lambda: [arg_domain, "domain"], {"limit": 100}, "Pivot Action"),
            "reverse_domain": ("reverse_domain", lambda: [arg_domain], {}, "Reverse Domain"),
            "reverse_ip": ("reverse_ip", lambda: [arg_ip], {"limit": 100}, "Reverse IP"),
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
                return json.dumps({"error": f"Unknown action '{arg_action}'."}, indent=2)
            
            method_name, args_fn, kwargs, label = dispatch[arg_action]
            args = args_fn()
            ok, payload = call_method(method_name, args, kwargs)
            
            if ok:
                # Safely extract response -> results from the payload
                try:
                    results = payload.get('response', {}).get('results', None)
                    return json.dumps({"results": results}, indent=2)
                except Exception as e:
                    return json.dumps({label: {"error": f"Failed to extract results: {e}"}}, indent=2)
            else:
                return json.dumps({label: {"error": payload}}, indent=2)
        
    except DomainToolsError as e:
        return json.dumps({"error": f"DomainTools client initialization error: {e}"}, indent=2)
    except Exception as e:
        return json.dumps({"error": f"Unexpected initialization error: {e}"}, indent=2)
    
    return None