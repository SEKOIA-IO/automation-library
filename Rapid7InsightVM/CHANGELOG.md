# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2026-11-05 - 1.0.0

### Added

- Initial release with the vulnerability asset connector and account validator
- Vulnerability findings collected from the InsightVM Cloud Integrations API v4 as delta windows (Create, Update and Close)
- Device of each finding with its short hostname, domain and IP address. An asset without a usable hostname (an IP address only, or no name) is skipped and counted, with a warning: the IP address is never used as hostname
- The checkpoint advances only when every batch of the cycle was pushed: after a failed push, the next cycle resumes from the last saved page (findings already accepted may be sent again)
- Size caps on the events: at most 1000 CVEs per finding, and the shared title, description and references only on the first CVE above 500 000 bytes
- Inconclusive statuses (skipped or failed checks) emit no event, instead of a Close or a Create
- A checkpoint reset (on a mapping change) keeps the comparison time: the next window closes the remediated findings and re-sends the open ones as Update
- Exponential backoff after a failed cycle, and retries of a window whose pages end before the announced total
