# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-12-19 - 1.0.8

### Fixed

- Fix the upload logs action

## 2025-12-18 - 1.0.7

### Fixed

- Fixed "user.name" issue when not mapped to thehive hostname

## 2025-12-17 - 1.0.6

### Fixed

- Fixed "Invalid json" error when adding observables by converting TLP and PAP levels from strings to integers as required by TheHive v5 API
- Added validation to skip observables with unknown data types instead of failing
- Improved data type conversion to ensure observable data is always a string

## 2025-12-16 - 1.0.5

### Added

- Add parameter to check SSL certificate validity (or not) in TheHive connector

## 2025-10-20 - 1.0.4

### Added

- Added 3 theHive actions to enrich an existing TheHive alert with:
    * a comment
    * new observables
    * logs as attachment

- Added a dedicated connector wrapper to centralize API interactions 

## 2025-09-08 - 1.0.3

### Added

- Add support for TLP and PAP in the create alert action

## 2025-07-31 - 1.0.2

### Fixed

- Set a default value if the sekoia_base_url parameter is not set in the configuration file

## 2025-07-16 - 1.0.1

### Added

- Add SEKOIA_BASE_URL parameter to allows users to change the region of sekoia

## 2024-05-27 - 1.0.0

### Added

- Add for the first time theHive action for the version 2 of thehive4py
