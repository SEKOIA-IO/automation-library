# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-12-13 - 1.1.0

### Changed

- Update Python version to 3.14

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
