# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## 2026-09-02 - 1.0.2

### Changed

- Harmonize connector logging by using `self.log(message=..., level=...)` consistently to improve log visibility in Loki/Grafana
- Add privacy-safe diagnostics when malformed HTTP header lines are ignored by reporting counts and malformation types only, without logging raw header line content

### Fixed

- Fix a crash in HTTP header parsing (`ValueError: not enough values to unpack`) caused by malformed header lines returned by the Akamai SIEM stream
- Make header parsing resilient to malformed input (missing separator, empty key, non-string headers) so event ingestion continues instead of stopping

## 2026-04-16 - 1.0.1

### Changed

- Optimize Akamai WAF event fetching by streaming events in chunks instead of accumulating a full page in memory

## 2026-01-07 - 1.0.0

### Changed

- Release module
