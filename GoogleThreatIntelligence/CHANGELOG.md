# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-01-30 - 0.1.14

### Fixed

- Action schemas: Move result fields to root level (remove `data` wrapper) for consistency across all actions:
  - Get Comments
  - Get IoC Report
  - Get Passive DNS
  - Get Vulnerability Associations
  - Get Vulnerability Report
  - Scan File
  - Scan URL

### Added

- Scan File: Additional unit tests for 100% code coverage (missing file_path argument, absolute paths handling, directory detection, error handling cases)

## 2025-12-21 - 0.1.13

### Fixed

- Scan File: copy file to a local temporary directory before uploading to handle remote storage (S3) file paths

## 2025-12-21 - 0.1.4

### Fixed

- Get Vulnerability Report: infinite loop with edge cases.

## 2025-12-19 - 0.1.3

### Fixed

- Add proxy support

## 2025-12-19 - 0.1.2

### Fixed

- Get Vulnerability Report: Extract all available fields from VT API response including counters, risk_rating, exploitation_state, exploit_availability, and other critical fields that were previously missing

## 2025-12-18 - 0.1.1

### Fixed

- Remove validation patterns as not working with jinja templates inputs