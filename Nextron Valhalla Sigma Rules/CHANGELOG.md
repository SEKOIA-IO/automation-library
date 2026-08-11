# Changelog

## 1.0.2 - 2026-08-11

- Replaced `logo.svg` with the official Valhalla brand mark.

## 1.0.1 - 2026-08-10

- `convert_parsed_to_ecs` no longer mutates the caller's parsed rule dict.
  A shallow copy is taken before the ECS-converted `detection` block is
  written, so callers can safely reuse the original Sigma structure.

## 1.0.0 - 2026-07-29

- Initial release.
