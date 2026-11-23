Plan: `docs/plans/2026-11-23-agent-reach-vps-implementation-plan.md`

Task 1: complete — public GitHub search adapter, provenance normalization, source-scoped deduplication, SQLite items/jobs, bounded retry, output checks, and worker CLI. Research tests pass in GitHub Actions.
Task 2: complete — read-only authenticated API, date/source/status filters, collection freshness metadata, Docker Compose API, systemd worker/timer, and live container verification against a read-only SQLite database.
Task 3: complete — pinned SkillSpector 2.13.6, SHA-256 verification, fail-closed policy, CI scan and report artifacts. The LEMO Opuscar v2.0.0 upstream skill was scanned and blocked by policy (TM2 HIGH, LP3 MEDIUM); no install or execution is approved pending human review.
Task 4: complete — manual LEMO provenance manifest, license guard, VPS operator guide, SQLite backup/retention script, restore procedure, and CI verification. The LEMO manifest tests passed; their initial red phase was not observed in CI and is explicitly recorded as a process gap in the plan.

VPS deployment remains unstarted because provider, region, server resources, network/access model, and operator-provisioned credentials have not been supplied. No secrets were requested or stored. The existing MT5/LLM files were not changed.
