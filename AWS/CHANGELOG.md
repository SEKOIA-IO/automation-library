# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2024-02-08 - 1.20.2

### Fixed

- Fix the way to compute the delay

## 2024-01-11 - 1.29.6

### Fixed

- Set MessageVisibilty to 1 minutes in the SQS wrapper

## 2024-01-05 - 1.29.5

### Changed

- Filter internal communications in Flowlogs parquet records

## 2023-12-22 - 1.29.4

### Add

- Combine messages into batch before sending it to the intake

## 2023-12-07 - 1.29.3

### Add

- Add beta flag to the Cloudfront connector

## 2023-12-07 - 1.29.0

### Add

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

## 2023-11-21 - 1.27

### Fixed

- Fix connector startup problems

## 2023-10-18 - 1.26

### Changed

- Refactoring of main functionality to make it more robust and easier to maintain

## 2023-10-27 - 1.25

### Changed

- Exclude GetRecords and GetObject events from collection

## 2023-10-26 - 1.24

### Changed

- Add new Flowlogs connector to collect VPC Flowlogs

## 2023-10-17 - 1.22.5

### Changed

- Add filters to collect only valid events

## 2023-09-21 - 1.22.3

### Changed

- Change the way to start the workers in the deprecated S3 flow logs connector
