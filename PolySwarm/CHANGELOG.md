# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 2026-10-13 - 1.0.0

### Added

- Sixteen actions, grouped under three verbs so an analyst can tell from the
  name what an action will do and what it will cost. Search reads what PolySwarm
  already knows and spends no scanning quota: SearchHash, SearchHashes,
  SearchUrl, SearchIp, SearchMetadata and SearchIoc. Scan submits an artifact to
  the engine marketplace and returns the multi-engine verdict: ScanFile, ScanUrl,
  ScanIp and ScanDomain. Sandbox detonates and returns where the report can be
  fetched: SandboxFile, SandboxUrl and SandboxIp. Report, ExtractIocs and
  AccountUsage round it out.
- A verdict is only reported once the assertion window has closed, and an engine
  that abstained is never counted as benign.
- SandboxCompleted trigger: start a playbook run when a detonation finishes,
  rather than holding a run open while waiting for one. A detonation that is
  still running when it falls off the newest page of tasks is followed by its own
  identifier until it finishes, and a fresh start records what has already
  finished without replaying it.
- PolySwarm Intel Feed connector: checkpointed ingestion of new results into a
  Sekoia intake, filtered by malware family, tag and PolySwarm score. The
  checkpoint only advances over events the intake confirmed, so delivery is at
  least once rather than silently lossy, and the connector reports the usual
  outgoing events, forward duration and events lag metrics.
- Account key validation when the configuration is saved, so a bad or expired
  key is caught then instead of by the first failing playbook.
- Indicators are validated before an API request is spent, and every action
  refuses the same things in the same words. A file named by a playbook is
  confined to the run data directory, and a URL whose host is a private,
  loopback, link-local, reserved, multicast or carrier-internal address is
  refused rather than published to a shared community.
- Waits are bounded everywhere, with the limit exposed to the analyst, so a slow
  scan or detonation delays a run rather than holding it open.
