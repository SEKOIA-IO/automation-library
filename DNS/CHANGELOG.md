# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 0.3.1 - 2026-10-26

### Changed

- Exclude the lint dependencies from the Docker image

## 0.3.0 - 2026-10-06

### Added

- Add support for Fission execution engine.

### Changed

- Update Python dependencies.

## 0.2.1 - 2026-07-30

### Changed

- Pin Docker base image to `python:3.14-bookworm` for reproducible runtime builds.

## 0.2.0 - 2026-07-23

### Changed

- Migrated module from Poetry to uv/mise.

## 0.1.0 - 2026-05-22

### Added

- Initial release of the DNS automation module with Reverse DNS lookup action.
