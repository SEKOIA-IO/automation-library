# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
