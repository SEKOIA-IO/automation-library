# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-16

### Added

- Initial release with the vulnerability asset connector, which collects the vulnerability findings of the assets
  assessed by the InsightVM Security Console (API v3) and publishes them as OCSF Vulnerability Finding events
- Account validator checking the credentials and the permissions on every endpoint used by the connector
- The connector keeps, per asset, the ids of the vulnerabilities still open at the last assessment (about 30 bytes
  per open finding in its checkpoint) to emit a Close event when a vulnerability disappears from an asset
