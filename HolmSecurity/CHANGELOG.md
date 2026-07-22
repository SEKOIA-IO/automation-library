# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-07-17

### Added

- Holm Security module with API token authentication
- Account validator that pings `GET /v2/devices?page_size=1`
- Device asset connector that collects agent-managed devices from `GET /v2/devices` and maps them to the OCSF Device Inventory Info model
