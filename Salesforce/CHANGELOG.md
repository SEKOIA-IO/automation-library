# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### 2024-02-01 - 1.5.3

#### Fix

- Use additional rate limits that comes from salesforce api

### 2024-02-02 - 1.5.2

#### Fixed

- Fix on the configuration option for frequency

### 2024-02-02 - 1.5.1

#### Added

- Configuration option for frequency

### 2024-01-24 - 1.4.12

#### Added

- Configuration option for salesforce api rate limit.
- Correct log message when is unable to authorize with salesforce api.

### 2023-11-21 - 1.4.11

#### Fixed

- Fix connector startup problems

### 2023-11-08 - 1.4.8

#### Fixed

- Fix rate limiting and change configuration of the module

### 2023-11-08 - 1.4.6

#### Fixed

- Fix metrics

### 2023-09-28 - 1.3.0

#### Changed

- Change the way of how events pushed to the intake. Use async wrapper for that

### 2023-07-20 - 1.2.5

#### Added

- add beta flag

### 2023-06-13 - 1.0.0

#### Added

- initial version of the connector
