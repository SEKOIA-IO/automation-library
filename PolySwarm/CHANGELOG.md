# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 2026-09-23 - 1.1.1

### Fixed

- The two hash lookups now fail with a plain message on an authentication
  failure, a usage limit or a gateway error, instead of letting the platform
  hand the playbook a Python traceback.
- File handling and the connector's state store now use the run data path the
  platform provides rather than assuming a local filesystem, which would have
  failed in a hosted environment while working locally.

## 2026-09-23 - 1.1.0

### Added

- Read only search actions: SearchUrl, SearchIp, SearchMetadata and SearchIoc.
  None of them submit anything or spend scanning quota, which until now no
  action could promise.
- Sandbox actions: SandboxFile, SandboxUrl and SandboxIp. Detonation is now a
  first class verb rather than something the report action did as a side
  effect, and a URL or an IP can be detonated, which a reputation lookup cannot
  answer at all.
- The sandbox image is chosen from the platform when none is named, so a
  detonation no longer depends on a hardcoded image identifier.

### Changed

- Report now only reads. It fetches the report for a detonation that already
  happened and never starts one, and it names the action to call instead.
- Every action description says which verb it belongs to, whether it spends
  quota, and which action to reach for when a different verb is wanted.
- Validation rules for addresses, URLs, domains and hashes live in one place, so
  every action refuses the same things with the same words.

### Fixed

- Every scan action declared each engine verdict as a boolean, while an engine
  that abstains answers null, which the platform really does return.
- The default sandbox image did not exist, so any detonation that relied on the
  default would have been refused by the platform.

## 2026-09-23 - 1.0.0

### Added

- Nine actions (ScanUrl, ScanIp, ScanDomain, ScanFile, SearchHash, SearchHashes,
  ExtractIocs, AccountUsage, Report) that submit indicators to PolySwarm and return
  multi-engine scan results, threat scores and detection metadata. A verdict is only
  reported once a scan's assertion window has closed, and engines that abstained are
  never counted as benign.
- SearchHashes: look up a list of hashes in one call, with the per-hash API cost
  stated plainly in the description.
- ExtractIocs: pull indicators out of text or a delivered file locally, with defanged
  forms handled and no API quota spent.
- Malware family set, tags and tag-derived actor attribution on SearchHash.
- SandboxCompleted trigger: emit an event when a sandbox detonation finishes, so a
  playbook no longer blocks while waiting for one.
- PolySwarm Intel Feed connector: scheduled, checkpointed ingestion of new results
  into a Sekoia intake, filtered by family, tag and PolySwarm score.
- Account key validation at configuration save time, so a bad or expired key is
  caught then instead of by the first failing playbook.
- A file named by a playbook is confined to the run data directory: absolute paths,
  parent traversal and symlinks pointing outside are refused.
