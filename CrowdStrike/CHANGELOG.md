# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2023-08-10

### Fixed

- Parallel processing of files should not block pushing events to intake

## [1.1.1] - 2023-06-21

### Fixed

- Properly declare the `queue_url` parameter in the collector configuration

## [1.1.0] - 2023-06-20

### Added

- Introduce the optional configuration parameter `queue_url` to specify the url of the SQS queue