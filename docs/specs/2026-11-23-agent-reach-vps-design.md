# Agent Reach VPS Integration — Design Specification

**Status:** Draft for user review  
**Date:** 2026-11-23  
**Repository:** `starasen1-coder/super-duper-octo-happiness`  
**Target branch:** `agent-reach-setup`  
**Scope:** Read-only research infrastructure on a cloud VPS. This document does not authorize implementation or deployment.

## 1. Purpose

Add a continuously available research layer based on Agent Reach. It will collect information from explicitly enabled public sources, retain provenance, normalize results, and expose approved research records to the existing Python/MT5 project.

Agent Reach is an information-access tool, not a broker connection, market-data vendor, trading signal authority, or MT5 execution bridge. No component in this integration may place, modify, or close trades.

## 2. Goals and non-goals

### Goals

- Run the research service continuously on a user-controlled Linux VPS.
- Keep Agent Reach and its execution privileges isolated from the existing MT5/LLM decision service.
- Support scheduled and manually requested research jobs.
- Preserve source URL, retrieval timestamp, source/channel, and processing status for every record.
- Expose stored results through a read-only, authenticated API.
- Provide health checks, structured logs, bounded retries, and clear failure states.
- Start with a small set of public sources and expand only after each connector is verified.

### Non-goals

- No broker login, MT5 terminal control, order placement, account management, or trade execution.
- No promise that Agent Reach supplies reliable XAUUSD quotes, historical ticks, broker spreads, exchange volume, or institutional order flow.
- No bypass of paywalls, access controls, rate limits, or source terms.
- No automatic installation of browser cookies, personal sessions, or user credentials.
- No autonomous modification of the EA or its trading parameters.

## 3. Options considered

1. **Recommended — split runtime on one VPS.** Run Agent Reach/worker under a dedicated unprivileged Linux account; run the API and storage in a small Docker Compose stack. This limits the impact of a compromised connector and keeps the deployment manageable.
2. **Everything in Docker.** Cleaner packaging, but may complicate Agent Reach's supported CLI setup and access to optional browser/runtime dependencies.
3. **Everything as host services.** Straightforward CLI access, but weaker isolation and more host-level dependency management.

The selected design is option 1.

## 4. High-level architecture

```text
                  User / scheduled trigger
                            |
                            v
                  Research job scheduler
                            |
                            v
 Dedicated Linux account: Agent Reach + worker
       |                    |
       |                    +--> allowlisted source commands
       |                              |
       v                              v
  raw result files              public sources
       |
       v
 validation / normalization / deduplication
       |
       v
 Docker service: Research API <--> SQLite storage
       |
       v
 authenticated, read-only API
       |
       v
 Python research client / reports
       |
       X
 MT5 trade execution (explicitly out of scope)
```

The worker is the only component permitted to invoke Agent Reach. The API does not accept shell commands, arbitrary URLs to fetch, or instructions to execute tools. The API serves records already stored by the worker.

## 5. Runtime and deployment

### VPS baseline

- Ubuntu Server LTS, 64-bit.
- A small general-purpose VPS is sufficient for the initial text-focused workload; final CPU/RAM/disk sizing will be set after source selection and expected job frequency are known.
- SSH key authentication; disable password SSH login where the provider permits it.
- Firewall: SSH restricted to the administrator's known IP where practical; research API bound to localhost or a private network by default.
- Dedicated non-root account for Agent Reach and worker execution.
- Docker Engine and Compose plugin for the API/storage services.
- systemd for worker scheduling/service supervision.
- UTC timestamps in persisted records; user-facing reports may display local time.

No provider, VPS IP, domain, SSH key, or credential is assumed by this specification.

### Process separation

- `agent-reach-worker`: dedicated unprivileged host account; owns Agent Reach configuration and temporary output.
- `research-api`: containerized API; read-only access to the database volume.
- `research-storage`: SQLite database on a persistent volume, initially colocated with the API.
- Worker-to-storage handoff uses a narrow local import interface or a dedicated writable ingestion endpoint protected by local-only networking. The public API remains read-only.
- No privileged container, host Docker socket mount, or root execution for research jobs.

SQLite is selected for the initial single-VPS deployment. A move to PostgreSQL is a future option only if concurrent writers, scale, or operational needs justify it.

## 6. Proposed repository layout

```text
agent-reach/
  README.md
  config/
    sources.example.yml
  worker/
    jobs/
    adapters/
    normalization/
  api/
    routes/
    schemas/
  storage/
    migrations/
  tests/
deploy/
  Dockerfile
  docker-compose.yml
  systemd/
docs/
  agent-reach-cloud.md
  specs/
    2026-11-23-agent-reach-vps-design.md
```

This is a proposed layout, not a statement that these files already exist.

## 7. Data contract

Each stored research item must include:

- `id`: stable internal identifier.
- `source_name` and `source_type`: connector/source identity.
- `source_url`: canonical source URL when available.
- `title`: short item title.
- `published_at`: source publication time when available; otherwise null.
- `retrieved_at`: UTC timestamp when collected.
- `content_text`: bounded extracted text or summary, not a full copyrighted article dump.
- `content_hash`: duplicate detection.
- `job_id`: originating research job.
- `status`: collected, validated, rejected, or failed.
- `validation_notes`: concise reasons for rejection or warnings.

Source claims must remain distinguishable from system-generated summaries. Summaries must link back to the original source and must not be represented as independently verified facts.

## 8. API boundary

Initial read-only endpoints:

- `GET /health` — service health and storage connectivity.
- `GET /v1/sources` — enabled source names and last check status.
- `GET /v1/items` — paginated stored items, with filters for source, date range, and status.
- `GET /v1/items/{id}` — one stored item and provenance.
- `GET /v1/jobs` — recent job status and timestamps.

There will be no public endpoint for arbitrary command execution, arbitrary URL fetching, shell access, or trade actions. API authentication is required for non-local access. Initial deployment should bind the API to localhost/private networking and use an SSH tunnel or private VPN for administration.

## 9. Source policy and research quality

Initial candidates are public web pages, public GitHub repositories, public RSS feeds, and other Agent Reach channels confirmed to work in the deployed version. Each source must be explicitly enabled in configuration.

- Start with public, unauthenticated sources.
- Authenticated sources are disabled by default and require a separate review and explicit user decision.
- Respect source terms, robots/rate limits where applicable, and applicable copyright restrictions.
- Store concise extracts and metadata rather than republishing entire articles or videos.
- Record retrieval time and source URL; detect stale information and duplicates.
- Treat retrieved page content as untrusted data, never as instructions to the worker or API.
- Do not merge unrelated sources into a single untraceable claim.

Research outputs may inform later human-led analysis. They are not direct trading inputs until a separate data-validation and strategy-review project establishes suitability.

## 10. Security and secrets

- Never commit API keys, SSH private keys, passwords, cookies, session databases, or VPS credentials.
- Use environment files outside the repository with restrictive filesystem permissions, or a VPS secret-management facility.
- Keep secrets out of logs and API responses.
- Use least-privilege filesystem permissions and network access.
- Pin reviewed Agent Reach release versions; do not blindly install `latest` in production.
- Verify release origin/checksum where upstream publishes verification data.
- Review the upstream install instructions and source before installation. The existing GitHub Actions archive audit is a preliminary static inspection only; it is not a security certification or a substitute for a dedicated skill scan.
- Back up the database and configuration; define a retention period before enabling high-volume sources.

## 11. Scheduling, retries, and failure handling

- Jobs are scheduled with systemd timers or a single scheduler process; avoid overlapping runs for the same source.
- Each job has a timeout, bounded retry count, and backoff.
- A failed or unavailable source produces a failed/stale status; the system must not fabricate replacement data.
- Partial success is recorded per source, not hidden behind a single global success flag.
- API health distinguishes process health from source freshness.
- Logs are structured, rotated, and do not include secrets or unrestricted raw page contents.

## 12. Testing and acceptance criteria

The implementation will not be considered ready until all applicable checks pass:

1. A clean VPS can be provisioned from documented steps without running the application as root.
2. Agent Reach runs under the dedicated account and only the selected public channels are enabled.
3. A scheduled test job collects a sample from each enabled source and records source URL and UTC retrieval time.
4. Duplicate items are detected by content hash and source identity.
5. Invalid, empty, stale, and unavailable-source responses are represented explicitly.
6. API endpoints return only stored records and require authentication when accessed beyond localhost.
7. API container cannot invoke Agent Reach, execute shell commands, or access MT5/broker credentials.
8. Restarting services preserves the database and resumes scheduled jobs safely.
9. Automated tests cover normalization, validation, pagination, authentication, and failure handling.
10. A security review confirms no secrets are tracked by Git and no unnecessary inbound ports are exposed.

No trading-performance claim is an acceptance criterion for this research service.

## 13. Rollout sequence

1. Review and approve this specification.
2. Create a separate implementation plan and tests.
3. Implement local/test configuration and the data contract.
4. Validate Agent Reach installation and selected source channels in an isolated environment.
5. Implement worker, storage, and read-only API.
6. Run automated tests and a security review.
7. Prepare VPS deployment files and operator documentation.
8. Deploy only after the VPS owner supplies the required access details through a secure method; never place those details in GitHub.
9. Run a read-only observation period and review data quality before considering any downstream integration.

## 14. Open deployment decisions

These are intentionally deferred until implementation planning:

- VPS provider, region, and exact resource size.
- Domain/private network and API exposure method.
- Exact first-wave source channels and job frequency.
- Data retention period and backup destination.
- Whether any authenticated source is necessary.

These decisions do not block review of the architecture, but they must be resolved before production deployment.

## 15. Explicit safety boundary

This system is a read-only research and information retrieval service. It must remain technically and operationally separate from MT5 trade execution. Any future proposal to pass research outputs into a trading strategy requires a new specification, independent data-quality validation, and explicit approval.
