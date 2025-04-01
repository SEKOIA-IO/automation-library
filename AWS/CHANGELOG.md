# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

## 2025-03-22 - 1.33.0

### Changed

- Refactor the way to read the content of S3 Objects and extract the events
  * Previously: S3 object content was read fully into memory before processing which could lead to performance bottlenecks and increased memory usage.
  * Now: The system leverages a streaming approach, allowing events to be extracted on-the-fly as data is read, thereby improving performance and reducing resource utilization.

## 2025-03-05 - 1.32.6

### Changed

- Refactor the way to define the number of max messages fetched from the SQS queue

## 2025-03-05 - 1.32.5

### Fixed

- Fix typing issue and reset the records list when pushing it

## 2025-03-04 - 1.32.4

### Fixed

- Memory leak issue when parse too many events

## 2025-02-20 - 1.32.3

### Changed

- Bump version of AWS SDK

## 2024-11-22 - 1.32.2

### Fixed

- Override the stop method due to an issue in the sdk (fix in progress)

## 2024-11-20 - 1.32.1

### Changed

- Add a new metric to count the number of discarded events by the AWS VPC Flowlogs connector

## 2024-10-30 - 1.32.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-10-24 - 1.31.7

### Fixed

- Fix the parameter `skip_first` for the AWS VPC Flowlogs trigger and connector to not collect the CSV header

## 2024-09-20 - 1.31.6

### Changed

- Change the way to monitor the age of messages

## 2024-09-11 - 1.31.5

### Fixed

- Change the connector dedicated to collect OCSF events

## 2024-08-01 - 1.31.4

### Added

- Add two new metrics to follow the messages age

## 2024-07-22 - 1.31.3

### Added

- Add connector for OCSF documents

## 2024-07-10 - 1.31.2

### Fixed

- Only pause the connector when messages were not collected

## 2024-07-08 - 1.31.1

### Changed

- Change the way to report the lag, when no events were collected
- Refactor the way to pause the connector

## 2024-05-28 - 1.31.0

### Changed

- Upgrade sekoia-automation-sdk

## 2024-05-21 - 1.30.14

### Fixed

- Fix typo for the collected events metric

## 2024-05-21 - 1.30.13

### Added

- Add a metric for collected events

## 2024-05-13 - 1.30.12

### Changed

- Remove delete_consumed_messages setting from trigger configuration

## 2024-04-24 - 1.30.11

### Changed

- Remove beta flag on AWS CLoudfront connector

## 2024-03-29 - 1.30.10

### Changed

- Use environment variable instead of configuration for batch size.

## 2024-03-29 - 1.30.9

### Changed

- Update `sekoia-automation-sdk` to the latest version (1.12.2) to fix
  support to intake batch URL.

## 2024-03-22 - 1.30.8

### Changed

- Update `sekoia-automation-sdk` to the latest version (1.12.1) to fix
  support for connectors (Batch URL) (not yet released).

## 2024-03-05 - 1.30.7

### Changed

- Filtering some ec2 events

## 2024-02-28 - 1.30.6

### Changed

- Set delete_consumed_messages option to true as default

## 2024-02-27 - 1.30.5

### Changed

- Upgrade sekoia-automation-sdk

## 2024-02-15 - 1.30.4

### Changed

- Removing ec2 events with the unsupported lists and allowing otherwise

## 2024-02-13 - 1.30.3

### Changed

- Change event_lags metrics from Histogram to Gauge

## 2024-02-08 - 1.30.2

### Fixed

- Fix the way to compute the delay

## 2024-01-11 - 1.29.6

### Fixed

- Set MessageVisibilty to 1 minutes in the SQS wrapper

## 2024-01-05 - 1.29.5

### Changed

- Filter internal communications in Flowlogs parquet records

## 2023-12-22 - 1.29.4

### Added

- Combine messages into batch before sending it to the intake

## 2023-12-07 - 1.29.3

### Added

- Add beta flag to the Cloudfront connector

## 2023-12-07 - 1.29.0

### Added

- Add for the first time the Cloudfront connector

## 2023-12-01 - 1.28.1

### Fixed

- Only pause, temporary, the connector if no events were forwarded

## 2023-12-01 - 1.28.0

### Changed

- Upgrade sekoia-automation-sdk


## 2023-11-21 - 1.27.2

### Fixed

- Register the flowlogs trigger

## 2023-11-21 - 1.27.1

### Fixed

- Bugfix with SQS connector push events to intake

## 2023-11-21 - 1.27.0

### Fixed

- Fix connector startup problems

## 2023-10-18 - 1.26.0

### Changed

- Refactoring of main functionality to make it more robust and easier to maintain

## 2023-10-27 - 1.25.0

### Changed

- Exclude GetRecords and GetObject events from collection

## 2023-10-26 - 1.24.0

### Changed

- Add new Flowlogs connector to collect VPC Flowlogs

## 2023-10-17 - 1.22.5

### Changed

- Add filters to collect only valid events

## 2023-09-21 - 1.22.3

### Changed

- Change the way to start the workers in the deprecated S3 flow logs connector
