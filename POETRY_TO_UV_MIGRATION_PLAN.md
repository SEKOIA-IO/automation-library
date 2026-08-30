# Poetry to uv/mise Migration Plan

Date: 2026-07-23

## Goal
Migrate all remaining Poetry-based automation modules to uv + mise using the repository `poetry-to-uv` skill conventions, without doing everything in one pass.

## Current Status
### Already migrated before this plan
- 1Password
- Flare
- HarfangLab
- LocateRisk
- Zimperium

### Pilot completed in this session
- DNS
- Tranco
- Whois

### Wave 1 completed in this session
- HTTP
- IKnowWhatYouDownload
- IPInfo
- IPtoASN
- Ilert
- Mandrill
- MokN
- PublicSuffix
- RSS
- Retarus
- USTA

### Wave 2 first batch completed in this session
- BinaryEdges
- Bitsight
- Censys
- CertificateTransparency
- Duo

### Wave 2 second batch completed in this session
- Fastly
- Git
- Glimps
- Jumpcloud
- Lookout

### Additional modules already migrated (outside the wave batches)
- Upwind
- Github (originally planned in Wave 6)

### Remaining scope
- Remaining modules to migrate: 81 (includes untracked `_utils` and `HolmSecurity`; 80 are covered by the waves below)
- Remaining planned effort: about 363.0 hours
- Criticity scale: 1 (easiest) to 10 (hardest)

## Incremental Delivery Strategy
- Work in small batches (2 to 4 modules per cycle).
- Prefer one pull request per module to simplify review and rollback.
- Keep migration order by risk: low criticity first, then medium, then high.
- At the end of each cycle, stop on a clean validation checkpoint.

## Standard Checklist Per Module
1. Rewrite `pyproject.toml` from Poetry to PEP 621 + `[tool.uv]` + `ruff` + `mypy` + pytest config.
2. Add `mise.toml` with `test`, `lint`, and `format` tasks.
3. Update `Dockerfile` to use uv sync and `/tmp -> /dev/shm` redirection block.
4. Bump module minor version in `manifest.json`.
5. Add changelog entry in `CHANGELOG.md`.
6. Run `uv lock` and remove `poetry.lock`.
7. Validate with:
   - `uv sync --frozen`
   - `uv run pytest tests/`
   - `uv run ruff check .`
   - `uv run ruff format --check .`
   - `uv run mypy .`
8. Ensure module folder is present in `automation-library.code-workspace` if needed.

## Waves

### Wave 1: Criticity 4 (estimated 2.5h each) - Completed
- HTTP
- IKnowWhatYouDownload
- IPInfo
- IPtoASN
- Ilert
- Mandrill
- MokN
- PublicSuffix
- RSS
- Retarus
- USTA

Estimated wave effort: 27.5h (completed)

### Wave 2: Criticity 5 (estimated 3h each) - In progress
- Mattermost
- MWDB
- Nybble
- Onyphe
- OSINTCollector
- Shodan
- ThinkstCanary
- Triage
- Ubika
- Utils
- Virustotal
- WatchGuard

Estimated wave effort: 66h total, 36h remaining

### Wave 3: Criticity 6 (estimated 4h each)
- Akamai
- BitDefender GravityZone
- BroadcomCloudSwg
- Cybereason
- Delinea
- DigitalShadows
- Eset
- ExtraHop
- HornetSecurity
- Imperva
- JIRA
- Mimecast
- NewRelic
- Nozomi
- OpenAI
- PagerDuty
- PandaSecurity
- RiskIQ
- Stormshield
- StormshieldSES
- Tehtris
- VadeCloud
- VadeSecure
- WithSecure

Estimated wave effort: 96h

### Wave 4: Criticity 7 (estimated 4.5h each)
- AzureMonitor
- BeyondTrust
- CatoNetwork
- Checkpoint
- CrowdStrike
- Darktrace
- DetectionRules
- Fortigate
- Google
- Lacework
- MicrosoftActiveDirectory
- MicrosoftOutlook
- MicrosoftWindowsServer
- Proofpoint
- Salesforce
- SentinelOneDeepVisibility
- SkyhighSecurity
- Sophos
- Tenable
- TrendMicro
- Trellix
- Vectra
- Wiz
- Zscaler

Estimated wave effort: 108h

### Wave 5: Criticity 8 (estimated 6h each)
- Azure
- CrowdStrikeFalcon
- CyberArk
- ElasticSearch
- MISP
- MicrosoftDefender
- MicrosoftEntraID
- Netskope
- Office365
- Okta
- PaloAltoCortexXDR
- PaloAltoXSIAM
- SentinelOne
- ServiceNow
- TheHive
- TheHiveV5
- TrendMicroVisionOne

Estimated wave effort: 102h

### Wave 6: Criticity 9 (estimated 7h each)
- AWS
- MicrosoftSentinel
- Sekoia.io

Estimated wave effort: 21h

## Suggested Batch Size Per Session
- Small session: 2 modules from current wave.
- Standard session: 3 modules from current wave.
- Large session: 4 modules from current wave.

## Resume Point For Next Session
Start with the next small batch from Wave 2:
1. Mattermost
2. MWDB
3. Nybble

After that, continue through the remaining Criticity 5 modules in order.

## Completion Gate
Before closing the migration project:
- No `poetry.lock` remains in targeted modules.
- No `[tool.poetry]` remains in targeted `pyproject.toml` files.
- All migrated modules have `uv.lock` and `mise.toml`.
- Dockerfiles use uv install flow with `/tmp` redirection.
