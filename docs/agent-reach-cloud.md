# Agent Reach: cloud integration preflight

## Status

This repository has a dedicated `agent-reach-setup` branch. The current ChatGPT session can edit GitHub files, but it does not expose a persistent shell in which to install Agent Reach or run its CLI.

The upstream project requires command execution. Its current install guide (1.6+) uses the official GitHub release archive with `uv`, then runs `agent-reach setup`. Do not install the similarly named PyPI package.

## What the preflight does

Run the GitHub Actions workflow **Agent Reach upstream audit** manually. It downloads the public upstream release archive and checks archive paths and source files for review. It does not execute, install, or enable Agent Reach.

This is not a security certification and is not a substitute for the dedicated skillguard scan. Installation remains blocked until the downloaded source has been scanned and reviewed in an environment with the scanner.

## Intended use in this project

Agent Reach is an information-access layer, not a market-data feed or an MT5 execution bridge. The initial channels can help read public web pages, YouTube material, GitHub repositories, V2EX and Bilibili. They do not guarantee reliable XAUUSD quotes, historical tick data, broker spreads, order-flow data, or exchange volume. Those must be sourced and validated separately before any research result is used by the EA.

Keep Agent Reach read-only. Do not add broker credentials, MT5 account passwords, trading API keys, browser cookies, or other secrets to GitHub Actions or this repository.

## Upstream references

- Install guide: https://raw.githubusercontent.com/Panniantong/Agent-Reach/main/docs/install.md
- English overview: https://github.com/Panniantong/Agent-Reach/blob/main/docs/README_en.md
- Troubleshooting: https://github.com/Panniantong/Agent-Reach/blob/main/docs/troubleshooting.md
