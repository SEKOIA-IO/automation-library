# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 2023-11-30 - 1.1.6

#### Fixed

- Increase to 1 seconds the delta from the start date when requested the last alerts

### 2023-11-29 - 1.1.5

#### Fixed

- Handle the pagination when listing the alerts
- Add 1 milliseconds to the start date when requested the last alerts, in order to exclude the last collected event

### 2023-11-28 - 1.1.4

#### Fixed

- Convert naive datetimes from events into aware ones

### 2023-11-28 - 1.1.3

#### Fixed

- Add the frequency property in the configuration

### 2023-11-28 - 1.1.2

#### Added

- Add timer to schedule calls

### 2023-11-24 - 1.1.1

#### Fixed

- Fix datetime parsing problem

### 2023-11-21 - 1.1.0

#### Fixed

- Fix connector startup problems

### 2023-10-06 - 1.0.0

#### Added

- initial version of the connector
