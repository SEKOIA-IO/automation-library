# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

### Added
- Initial release of the DomainTools module
- **Domain Reputation** action: assess the risk score and reputation of a domain
- **Lookup Domain** action: retrieve comprehensive WHOIS, DNS, and infrastructure data for a domain
- **Pivot Action** action: pivot on domain attributes (IP, email, nameserver, SSL, etc.) to find connected domains
- **Reverse Domain** action: find domains associated with a given domain attribute
- **Reverse Email** action: find domains registered with a given email address
- **Reverse IP** action: find domains hosted on a given IP address
- **Iris Investigate Reverse IP** action: query DomainTools Iris Investigate API to find domains associated with an IP address, returning comprehensive intelligence including risk scores, WHOIS data, SSL certificates, and DNS records
