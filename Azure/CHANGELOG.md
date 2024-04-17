# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2024-04-09 - 2.4.10

### Fixed

- Fix the way to handle the Azure Key Vault Events

## 2024-04-09 - 2.4.9

### Added

- Add new connector to work with Azure Key Vault events

## 2024-04-09 - 2.4.8

### Changed

- Pause the blob storage connector when no records were forwarded

## 2024-04-09 - 2.4.7

### Changed

- Add more logs
- Refactor get_azure_blob_data with a new method that get the most recent blobs

## 2024-04-08 - 2.4.6

### Fixed

- Exclude empty lines from the records when processing through Azure Blob Storage

## 2024-03-21 - 2.4.5

### Added

- Add chunk size usage to Azure Blob Storage connector

## 2024-03-21 - 2.4.4

### Added

- Add new Azure Blob Storage connector. This connector is generic and do no actions on events

### Changed

- Rebrand the previous Azure Blob Storage connector into one specific for Azure Network Watcher.

## 2024-03-01 - 2.4.3

### Changed

- Add support for gzipped file in Azure Blob Storage

## 2024-02-13 - 2.4.2

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2024-01-23 - 2.2.4

### Changed

- Use uamqp library instead of pyamqp for the EventHub connector

## 2023-12-12 - 2.2.3

### Fixed

- Fix the way to handle events in a message

## 2023-12-11 - 2.2.2

### Changed

- Change the way to extract records from the messages

## 2023-12-06 - 2.2.1

### Fixed

- Use a single loop

## 2023-11-30 - 2.2.0

### Changed

- Converted to async for better performance

### Removed

- Removed deprecated metrics code

## 2023-11-21 - 2.1.3

### Fixed

- Fix connector startup problems

## 2023-11-08 - 2.1.2

### Fixed

- Fix metrics

## 2023-10-24 - 2.1.1

### Fixed

- Added Beta Flag for Azure Blob Storage

## 2023-10-20 - 2.0.1

### Fixed

- Fix the import of connector

## 2023-10-02 - 2.0.0

### Added

- Add new connector to fetch events from Azure Blob storage.

### Changed

- Refactor the module
