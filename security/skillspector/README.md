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

The CI workflow scans only the harmless fixture in this repository. It demonstrates the scanner and policy integration; it does not approve any third-party skill.
