# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-12

### Added

- Add 4 actions:
  - `Scan URL`: submit a URL to urlscan.io, wait for the scan and return a curated summary with a ready-to-post Markdown comment
  - `Get scan result`: return the same summary for an existing scan
  - `Download scan screenshot`: store the PNG screenshot of a scan as a file of the playbook run
  - `Search`: search existing scans by indicator or query, with `search_after` pagination
- Add an account validator checking the urlscan.io API key
- Refuse internal addresses before a URL is submitted to urlscan.io
