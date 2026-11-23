# SkillSpector review summary: LEMO Opuscar v2.0.0

**Decision: BLOCK — do not install or execute pending human review.**

- Target repository: https://github.com/lemomo-ai/lemo-opuscar
- Pinned commit: `2ef41cca9a9330c96c00ec0d8d40807b4b062bb4`
- Upstream tag: `v2.0.0` (unsigned)
- Scanner: NVIDIA SkillSpector `2.13.6`
- Mode: static analysis, `--no-llm`
- Scan date: 2026-11-23
- Coverage: 100%, complete with caveats
- Aggregate score: 31 / MEDIUM / CAUTION
- Highest finding: HIGH
- Local policy result: **block**

## Findings

1. **TM2 — HIGH, confidence 0.75**
   - Location: `scripts/setup.sh:99`
   - Category: Tool Misuse / Chaining Abuse.
   - The scanner flags a chained shell setup operation containing removal and recreation of the local `.venv` directory. This may be an ordinary environment-repair operation, but it needs manual review of the full script and its execution context before approval.

2. **LP3 — MEDIUM, confidence 0.70**
   - Location: `SKILL.md:1`
   - Category: MCP Least Privilege.
   - The skill declares no tool scope while the package contains shell capabilities. Review the host agent's permission model and whether shell execution can be constrained.

The report's overall recommendation is CAUTION, but the project's fail-closed policy blocks any HIGH finding even when the aggregate score is lower. This is a security-review gate, not a finding that the project is malicious.

## Handling decision

- Do not install the upstream skill on the VPS.
- Do not execute its setup script.
- Keep the repository integration limited to a provenance manifest; no renderer is invoked.
- Reconsider only after a human reviews the exact pinned source, setup script, shell permissions, and license boundaries, then records explicit approval for that commit.

The complete machine-readable report and manifest were retained as a GitHub Actions artifact for 14 days from the scan run. The artifact is separate from this concise review summary.
