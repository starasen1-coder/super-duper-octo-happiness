# Agent Reach Research VPS Implementation Plan

> **For agentic workers:** Use the host's available task-by-task implementation workflow. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver an isolated, read-only research service on a cloud VPS using Agent Reach, with pre-install skill scanning and optional visual report rendering.

**Architecture:** Agent Reach runs under a dedicated unprivileged host account and a bounded worker. The worker imports provenance-bearing research records into SQLite, served by a read-only FastAPI API. SkillSpector runs separately as a no-secret pre-install gate; LEMO Opuscar runs only as an optional isolated renderer over curated report inputs.

**Tech Stack:** Ubuntu Server LTS, Python, Agent Reach CLI, FastAPI, Pydantic, SQLite, Docker Compose, systemd timers, NVIDIA SkillSpector, Node.js/Python rendering dependencies for optional LEMO Opuscar, pytest, GitHub Actions.

## Global Constraints

- Research-only service; no broker login, MT5 terminal control, order placement, account management, or trade execution.
- Agent Reach worker is the only component allowed to invoke Agent Reach.
- API serves stored records only; it does not execute shell commands or fetch arbitrary URLs.
- Public, unauthenticated sources only in the first rollout; each source is explicitly allowlisted.
- Retrieved content is untrusted data, never worker instructions.
- Do not bypass access controls, paywalls, rate limits, or source terms.
- Store concise extracts and metadata, not full copyrighted article/video contents.
- Never commit API keys, SSH keys, passwords, cookies, session databases, broker credentials, or trading API keys.
- Agent Reach, SkillSpector, API/storage, and LEMO Opuscar must run with separate least-privilege boundaries.
- Pin reviewed tool versions; do not install an unreviewed latest release or execute remote install scripts directly.
- A scanner pass is not a security guarantee; human review remains required.
- LEMO Opuscar is optional; text/HTML/PNG reporting must work without it.
- Existing `proxy_server.py`, `LLM_Advisor.mq5`, and the MT5/LLM path are not modified by this project.

---

## Repository evidence and proposed layout

Observed on branch `agent-reach-setup`:
- `proxy_server.py`: current FastAPI LLM decision proxy with `POST /decide` and `GET /health`.
- `LLM_Advisor.mq5`: existing EA sends snapshots to the local proxy and contains trade calls; explicitly outside this project.
- `requirements.txt`: currently unpinned Python dependencies, including FastAPI/Pydantic and Windows-only MetaTrader5.
- `.env.example`: currently contains an Anthropic key placeholder and model setting; do not reuse it for the research service.
- `docs/agent-reach-cloud.md`: preflight notes and current limitations.
- `.github/workflows/agent-reach-audit.yml`: manual workflow that downloads and statically inspects the Agent Reach archive without executing it.

The following paths are **proposed** and do not yet exist unless verified during implementation:
- `agent-reach/worker/`: source adapters, scheduling, validation and ingestion.
- `agent-reach/api/`: read-only API routes and response schemas.
- `agent-reach/storage/`: SQLite schema and repository access.
- `agent-reach/tests/`: focused automated tests.
- `deploy/`: Compose, container definitions and systemd units.
- `security/skillspector/`: scanner wrapper and report policy.
- `visual-reports/lemo-opuscar/`: isolated rendering adapter and operator notes.

## Task 1: Agent Reach worker, provenance contract, and SQLite ingestion

**Files:**
- Create: `agent-reach/worker/config.py`
- Create: `agent-reach/worker/runner.py`
- Create: `agent-reach/worker/adapters/agent_reach_cli.py`
- Create: `agent-reach/worker/normalize.py`
- Create: `agent-reach/storage/schema.sql`
- Create: `agent-reach/storage/repository.py`
- Create: `agent-reach/tests/test_normalize.py`
- Create: `agent-reach/tests/test_repository.py`
- Create: `agent-reach/config/sources.example.yml`

**Interfaces:**
- Consumes: allowlisted source configuration; Agent Reach CLI output captured by the worker.
- Produces: `ResearchItem` records with `id`, `source_name`, `source_type`, `source_url`, `title`, `published_at`, `retrieved_at`, `content_text`, `content_hash`, `job_id`, `status`, and `validation_notes`.
- Storage interface: `insert_items(items: Sequence[ResearchItem]) -> IngestResult`; `list_items(filters: ItemFilters) -> Page[ResearchItem]`; `get_item(item_id: str) -> ResearchItem | None`.

- [ ] **Step 1: Add focused failing tests**

Test valid item persistence and retrieval; duplicate content hash from the same source is not inserted twice; the same content from a different source retains separate provenance; absent publication time remains null; empty CLI output produces a failed/empty job result rather than fabricated content; malformed records are rejected with a recorded reason.

- [ ] **Step 2: Verify the relevant failure**

Run: `python -m pytest agent-reach/tests/test_normalize.py agent-reach/tests/test_repository.py -q`

Expected: collection fails because the proposed modules and interfaces do not yet exist.

- [ ] **Step 3: Implement the minimum behavior**

Create the SQLite schema for research items and jobs. Implement deterministic serialization, source-scoped content hashing, bounded text storage, UTC retrieval timestamps, and explicit collected/validated/rejected/failed states. Implement a CLI adapter that invokes only configured Agent Reach commands, uses an argument array rather than shell interpolation, enforces per-job timeout, captures bounded stdout/stderr, and never accepts arbitrary user-supplied commands or URLs. Keep source-specific parsing isolated in adapters. Do not invent publication timestamps when absent.

- [ ] **Step 4: Verify the focused pass**

Run: `python -m pytest agent-reach/tests/test_normalize.py agent-reach/tests/test_repository.py -q`

Expected: all item-contract, deduplication, empty-result, and malformed-record tests pass.

- [ ] **Step 5: Run the affected integration check**

Run: `python -m pytest agent-reach/tests -q`

Expected: worker and storage tests pass without requiring MT5, broker credentials, or an external model API key.

- [ ] **Step 6: Commit the passing deliverable**

```bash
git add agent-reach/worker agent-reach/storage agent-reach/config agent-reach/tests
git commit -m "feat: add Agent Reach research ingestion"
```

## Task 2: Read-only Research API and isolated service deployment

**Files:**
- Create: `agent-reach/api/app.py`
- Create: `agent-reach/api/schemas.py`
- Create: `agent-reach/api/routes/health.py`
- Create: `agent-reach/api/routes/sources.py`
- Create: `agent-reach/api/routes/items.py`
- Create: `agent-reach/api/routes/jobs.py`
- Create: `agent-reach/tests/test_api.py`
- Create: `deploy/Dockerfile`
- Create: `deploy/docker-compose.yml`
- Create: `deploy/systemd/agent-reach-worker.service`
- Create: `deploy/systemd/agent-reach-worker.timer`
- Create: `deploy/.dockerignore`

**Interfaces:**
- Consumes: Task 1 storage repository.
- Produces: `GET /health`, `GET /v1/sources`, `GET /v1/items`, `GET /v1/items/{id}`, and `GET /v1/jobs`.
- API list filters: source, date range, status, page size and cursor/page token.
- API response never includes environment variables, secret values, raw process stderr, or unbounded source content.

- [ ] **Step 1: Add focused failing tests**

Test each endpoint with seeded SQLite records; verify pagination is stable; verify unknown IDs return 404; verify invalid pagination/filter values return 422; verify API access policy denies unauthenticated non-local requests; verify health distinguishes process/database availability from source freshness.

- [ ] **Step 2: Verify the relevant failure**

Run: `python -m pytest agent-reach/tests/test_api.py -q`

Expected: tests fail because the API modules and routes do not yet exist.

- [ ] **Step 3: Implement the minimum behavior**

Implement read-only route handlers using the repository interface. Do not expose write, command, arbitrary-fetch, or trade endpoints. Configure the API container with a read-only database mount. Keep ingestion on a narrow local-only path owned by the worker; do not expose a public ingestion route. Bind the API to localhost/private networking by default. Add authentication before any non-local exposure. Run the worker as a dedicated unprivileged host account through systemd; prevent overlapping jobs and set bounded runtime/timeouts. Do not mount the Docker socket or expose host credentials to containers.

- [ ] **Step 4: Verify the focused pass**

Run: `python -m pytest agent-reach/tests/test_api.py -q`

Expected: endpoint, pagination, authentication, and health-state tests pass.

- [ ] **Step 5: Run the affected integration check**

Run: `docker compose -f deploy/docker-compose.yml config`

Expected: Compose configuration validates, API has no Agent Reach CLI dependency, and the database volume is persistent and mounted read-only in the API container. On a Linux test host, start the stack and verify `GET /health` succeeds while unauthenticated non-local requests are denied.

- [ ] **Step 6: Commit the passing deliverable**

```bash
git add agent-reach/api agent-reach/tests/test_api.py deploy
git commit -m "feat: add read-only research API deployment"
```

## Task 3: SkillSpector pre-install security gate

**Files:**
- Create: `security/skillspector/README.md`
- Create: `security/skillspector/scan.py`
- Create: `security/skillspector/policy.yml`
- Create: `security/skillspector/tests/test_policy.py`
- Create: `.github/workflows/skillspector-scan.yml`

**Interfaces:**
- Consumes: an explicitly selected repository, archive, directory, or skill package plus a pinned SkillSpector version.
- Produces: scan metadata (target, immutable revision/version, scanner version, timestamp), report artifacts, and a pass/review/block decision.
- The scan workflow has no production secrets, no write token, no Docker socket, and read-only access to scan inputs.

- [ ] **Step 1: Add focused failing tests**

Test policy mapping for clean findings, informational findings, high/critical findings, scanner failure, unavailable report, and unpinned target version. High/critical or incomplete scans must not be treated as approved.

- [ ] **Step 2: Verify the relevant failure**

Run: `python -m pytest security/skillspector/tests/test_policy.py -q`

Expected: tests fail because the policy evaluator does not yet exist.

- [ ] **Step 3: Implement the minimum behavior**

Pin the reviewed SkillSpector release and installation method after checking its upstream documentation and license. Invoke it in a disposable CI job/container using read-only inputs. Preserve JSON/Markdown/SARIF outputs where the pinned version supports them. Store the exact target revision and scanner version alongside the report. Map findings to pass/review/block using a checked-in policy; scanner crashes, missing reports, unpinned targets, and high/critical findings block automatic approval. Require a human approval record before a package can be added to the project's enabled extension list. Do not let the scanner install or activate scanned packages.

- [ ] **Step 4: Verify the focused pass**

Run: `python -m pytest security/skillspector/tests/test_policy.py -q`

Expected: every policy mapping produces the expected decision, including fail-closed behavior on scanner errors.

- [ ] **Step 5: Run the affected integration check**

Run the GitHub Actions workflow manually against a harmless public sample skill pinned to a commit.

Expected: the workflow emits a versioned report artifact, has no secrets or write permissions, and does not install or execute the scanned skill.

- [ ] **Step 6: Commit the passing deliverable**

```bash
git add security/skillspector .github/workflows/skillspector-scan.yml
git commit -m "feat: add SkillSpector pre-install gate"
```

## Task 4: Optional LEMO Opuscar renderer, operational hardening, and documentation

**Files:**
- Create: `visual-reports/lemo-opuscar/README.md`
- Create: `visual-reports/lemo-opuscar/render.py`
- Create: `visual-reports/lemo-opuscar/tests/test_manifest.py`
- Create: `deploy/backup-research-db.sh`
- Create: `deploy/README.md`
- Modify: `docs/agent-reach-cloud.md`
- Modify: `README.md`

**Interfaces:**
- Consumes: curated report manifest containing report ID, input file paths, renderer version, output destination, and asset-credit metadata.
- Produces: optional rendered media plus a manifest recording input report ID, renderer version, output checksum, and applicable third-party asset credits.
- Renderer runs manually or as a separately isolated job; it has no connector credentials, production secrets, database write access, or MT5 access.

- [ ] **Step 1: Add focused failing tests**

Test that renderer input paths must remain inside the designated report-input directory; secret-like environment values are not forwarded; generated manifest records input report ID, renderer version and credits; renderer failure leaves the original report intact; text/HTML/PNG report generation does not depend on LEMO Opuscar being installed.

- [ ] **Step 2: Verify the relevant failure**

Run: `python -m pytest visual-reports/lemo-opuscar/tests/test_manifest.py -q`

Expected: tests fail because the renderer manifest contract does not yet exist.

- [ ] **Step 3: Implement the minimum behavior**

Review LEMO Opuscar upstream version, dependencies, license boundaries, and resource needs before pinning. Keep code and style/documentation asset licenses distinct. Invoke the renderer only on curated, non-sensitive reports in a separate isolated runtime. Do not install optional voice/music/HDRI/model assets by default. Keep a non-video report path. Add database backup/restore instructions, log rotation, retention controls, source freshness reporting, firewall/network binding guidance, and operator instructions. Document that VPS deployment requires a separate explicit deployment authorization and secure out-of-band access provisioning.

- [ ] **Step 4: Verify the focused pass**

Run: `python -m pytest visual-reports/lemo-opuscar/tests/test_manifest.py -q`

Expected: path isolation, metadata, failure preservation, and renderer-independent report tests pass.

- [ ] **Step 5: Run the affected integration check**

Run: `python -m pytest agent-reach/tests security/skillspector/tests visual-reports/lemo-opuscar/tests -q`

Expected: all research ingestion, API, scanner policy, and rendering adapter tests pass. Also run `docker compose -f deploy/docker-compose.yml config` and verify backup/restore on a disposable database.

- [ ] **Step 6: Commit the passing deliverable**

```bash
git add visual-reports deploy docs/agent-reach-cloud.md README.md
git commit -m "feat: add optional visual reports and VPS operations docs"
```

## Unresolved deployment decisions

These decisions affect production deployment, not the implementation of the isolated local/test components:

1. VPS provider, region, CPU/RAM/disk size.
2. API access model: localhost with SSH tunnel, private VPN, or domain plus authenticated reverse proxy.
3. Initial public source allowlist and per-source collection frequency.
4. Research-record retention period and backup destination/retention.
5. Whether any authenticated source is necessary; default remains disabled.
6. Whether LEMO Opuscar video output is needed in the first release; default remains disabled.
7. Whether the deployment should use a separate subdomain and TLS termination, or remain private-only.

No VPS deployment, secret provisioning, authenticated-source enablement, or downstream MT5 integration is included in these implementation tasks.
