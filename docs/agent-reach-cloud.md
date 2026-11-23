# Agent Reach: cloud integration preflight

## Status

This repository has a dedicated `agent-reach-setup` branch. The current ChatGPT session can edit GitHub files, but it does not expose a persistent shell in which to install Agent Reach or run its CLI.

The upstream project requires command execution. The reviewed baseline is Agent Reach v1.6.1 from the official versioned GitHub release asset, verified by SHA-256 in `security/tool-versions.json`. The similarly named PyPI package is not this project and must not be installed.

The current worker uses the public GitHub REST backend explicitly (`--backend github-api`) and does not require a GitHub token. Authenticated, optional, and experimental channels remain disabled. Agent Reach itself prints one JSON envelope per command in v1.6+; the adapter validates the response before importing records.

## What the preflight does

Run the GitHub Actions workflow **Agent Reach upstream audit** manually. It downloads the public upstream release archive and checks archive paths and source files for review. It does not execute, install, or enable Agent Reach.

This is not a security certification and is not a substitute for the dedicated skillguard scan. Installation remains blocked until the downloaded source has been scanned and reviewed in an environment with the scanner.

## Intended use in this project

Agent Reach is an information-access layer, not a market-data feed or an MT5 execution bridge. The initial channels can help read public web pages, YouTube material, GitHub repositories, V2EX and Bilibili. They do not guarantee reliable XAUUSD quotes, historical tick data, broker spreads, order-flow data, or exchange volume. Those must be sourced and validated separately before any research result is used by the EA.

Keep Agent Reach read-only. Do not enable login channels, browser session reuse, or optional/experimental sources in the first rollout. Do not add broker credentials, MT5 account passwords, trading API keys, browser cookies, GitHub tokens, or other secrets to GitHub Actions or this repository.

The VPS worker is separate from the MT5/LLM prototype. The API is read-only and binds to loopback by default. See [deployment instructions](../deploy/README.md), [pinned tool versions](../security/tool-versions.json), and the [implementation plan](plans/2026-11-23-agent-reach-vps-implementation-plan.md).

## Upstream references

- Install guide: https://raw.githubusercontent.com/Panniantong/Agent-Reach/main/docs/install.md
- English overview: https://github.com/Panniantong/Agent-Reach/blob/main/docs/README_en.md
- Troubleshooting: https://github.com/Panniantong/Agent-Reach/blob/main/docs/troubleshooting.md
