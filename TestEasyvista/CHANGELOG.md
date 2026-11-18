# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-11-18

### Added

- Initial version: test module holding only the `EasyVista Devices` asset connector of EasyVista Service Manager (no playbook actions), to test custom asset connectors. It collects the assets of `GET /assets` that have a usable network identifier, skips removed and recycled assets, pushes only new or changed devices and maps them to the OCSF Device Inventory Info model
- Account validation reads one request, or one asset when the REST API profile is denied access to requests (`403`)
