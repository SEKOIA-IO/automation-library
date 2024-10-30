# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 1.11.0 - 2024-10-30

### Changed

- Upgrade sekoia-automation-sdk

## 1.10.2 - 2024-09-30

### Fixed

- Set MessageVisibility to one minute

## 1.10.1 - 2024-07-09

### Changed

- Filter on specific event_simpleName values

## 1.10.0 - 2024-05-28

### Changed

- Upgrade sekoia-automation-sdk

## 1.9.1 - 2024-02-13

### Changed

- Change event_lags metrics from Histogram to Gauge

## 1.8.2 - 2023-11-21

### Fixed

- Fix connector startup problems

## 1.8.1 - 2023-11-08

### Fixed

- Fix metrics

## 1.7.1 - 2023-10-02

### Changed

- Remove the alpha/beta flag

## 1.7.0 - 2023-09-28

### Changed

- Change the way of how events pushed to the intake. Use async wrapper for that

## 1.6.4 - 2023-09-04

### Fixed

- Change the way to set the maximum number of messages got when reading the SQS queue

## 1.6.2 - 2023-08-28

### Fixed

- Use custom async client session instead of `requests`

## 1.6.1 - 2023-08-25

### Fixed

- Add more logs
- Fix the way to read the content of objects

## 1.2.0 - 2023-08-10

### Fixed

- Parallel processing of files should not block pushing events to intake

## 1.1.1 - 2023-06-21

### Fixed

- Properly declare the `queue_url` parameter in the collector configuration

## 1.1.0 - 2023-06-20

### Added

- Introduce the optional configuration parameter `queue_url` to specify the url of the SQS queue
