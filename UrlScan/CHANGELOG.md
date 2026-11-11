# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2026-11-11 - 1.0.0

### Added

- Scan URL action: submit a URL to urlscan.io, wait for the scan and return a curated summary with a ready-to-post Markdown comment
- Get scan result action: return the same summary for an existing scan
- Download scan screenshot action: store the PNG screenshot of a scan as a file of the playbook run
- Search action: search existing scans by indicator or query, with `search_after` pagination
- Account validator checking the urlscan.io API key
- Internal addresses are refused before a URL is submitted to urlscan.io
