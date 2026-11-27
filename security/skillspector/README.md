# SkillSpector pre-install gate

This gate uses NVIDIA SkillSpector **v2.13.6** (Apache-2.0), pinned by release asset URL and SHA-256 in `security/tool-versions.json`.

The scanner is installed and run only in an isolated CI job. It receives no production secrets, write token, Docker socket, broker data, browser sessions, or production filesystem mounts. It scans a local, revision-pinned checkout with static analysis (`--no-llm`) and fails closed on incomplete inspection.

## Operator flow

1. Clone the candidate skill repository at a specific commit in a disposable workspace.
2. Record and verify the exact 40-character Git commit.
3. Run `python security/skillspector/scan.py --target /path/to/checkout --revision <commit> --output-dir /tmp/skillspector`.
4. Review the JSON report and manifest. A `pass` is only a scanner-policy result, not a security guarantee.
5. A human must approve the exact repository, commit, report, and required permissions before any installation.
6. Do not install a package solely because its scanner report says `pass`.

On every relevant push, CI scans the harmless in-repository fixture and verifies policy tests. A separate on-demand workflow-dispatch job scans a selected public GitHub candidate at its immutable commit; it does not approve or install that candidate.

The scanner wrapper and policy are Python modules under the `security.skillspector` package. The CI workflow verifies the wheel digest before installation and runs the scanner with no LLM provider credentials.

## Scan any public GitHub candidate

Use the `SkillSpector security gate` GitHub Actions workflow with:
- `target_repository`: `owner/repository` (not an arbitrary URL);
- `target_revision`: exact 40-character lowercase commit SHA;
- `target_subdirectory`: the skill directory within that checkout, or `.`.

The remote scanner fetches that exact commit, verifies the checked-out SHA, rejects path traversal, and runs SkillSpector with `--no-llm`. The LEMO workflow step now explicitly asserts successful scanner execution, a `block` decision, a report digest, and the expected HIGH finding instead of silently tolerating any scanner error. Candidate content is never installed or executed. The job has read-only repository permissions, no secrets, and preserves its report as an artifact. A review/block result fails the scan job; inspect the artifact before making any decision.

## Extension admission registry

`approved-extensions.json` is intentionally empty. Unknown extensions are denied. A registry entry is valid only when it pins all of:
- extension ID and canonical HTTPS GitHub repository;
- exact 40-character commit SHA;
- pinned scanner version and `pass` decision;
- exact SHA-256 digest of the scanner JSON report;
- human approver, timestamp, and a non-empty explicit permission list.

Before enabling an extension, obtain the scan artifact, review the source and requested permissions, and add an approval record through a reviewed change. Use `python security/skillspector/require_approved.py --extension-id <id> --repository https://github.com/<owner>/<repo> --revision <commit> --report-sha256 <digest>` as the admission check. The command exits non-zero unless every field matches exactly. Any source revision or report change requires a new scan and approval.

The registry check is a local admission control, not a substitute for repository governance. Configure GitHub branch protection/rulesets outside this code so changes to `security/skillspector/approved-extensions.json` require an independent security review. The GitHub API returned no repository rulesets; branch-protection details could not be read with the connected integration's permissions. Therefore independent approval enforcement is not verified and must be configured by the repository owner before adding any extension.

## Scope and limits

SkillSpector is static analysis, not a proof of safety, a runtime sandbox, or a trading-strategy validator. It does not validate live MCP protocol behavior, Python package vulnerability databases, agent runtime permissions, or broker/MT5 behavior; those require separate controls and tests. The current workflow scans an explicitly supplied public GitHub candidate; it does not crawl every public repository or automatically install extensions. Private repositories and authenticated sources are not supported by this workflow. The first rollout has no approved third-party extensions.
