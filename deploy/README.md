# Research VPS deployment

This document describes a private, research-only deployment. It does not deploy MT5 or connect to a broker.

## Components

- Agent Reach runs under the dedicated `agent-reach` Linux account.
- The worker runs as a systemd oneshot service and writes SQLite data to `/var/lib/agent-reach`.
- The API runs in Docker Compose with a read-only database mount and binds only to `127.0.0.1:8080`.
- SkillSpector runs separately in CI as a pre-install security gate.
- LEMO Opuscar is an optional, separately invoked renderer and is not installed by this deployment.

## Prerequisites

Use an Ubuntu LTS VPS with a dedicated non-root account, Docker Engine + Compose plugin, Python 3.12, and a reviewed Agent Reach release. Configure the host firewall to deny inbound access to port 8080. Use an SSH tunnel for private API access unless a separately reviewed private VPN/reverse-proxy design is approved.

## One-time host preparation

1. Create the `agent-reach` system user and group.
2. Create `/opt/agent-reach/app`, `/opt/agent-reach/venv`, `/etc/agent-reach`, and `/var/lib/agent-reach`; set ownership so only the service account can write application state and data.
3. Check out the approved project branch into `/opt/agent-reach/app`.
4. Create the Python environment and install `agent-reach/requirements-api.txt`.
5. Install Agent Reach from its versioned GitHub release ZIP, not from PyPI. The reviewed baseline is Agent Reach **v1.6.1**. Verify the downloaded release asset against the SHA-256 digest in `security/tool-versions.json` before installation.
6. Run `agent-reach version` and `agent-reach channels`. Do not run setup for optional or experimental channels.
7. Copy `agent-reach/config/sources.example.json` to `/etc/agent-reach/sources.json` and review each source/query. Only the public GitHub API backend is enabled by the worker. Do not add logged-in sources, cookies, session directories, or API keys.
8. Install the systemd unit files from `deploy/systemd`, then run one controlled worker invocation and inspect its JSON output and logs before enabling the timer.
9. Confirm that `/var/lib/agent-reach/research.sqlite3` exists and is readable by the API container's numeric UID 10001. The API container must never have write access to this directory. Set `AGENT_REACH_API_GID` to the numeric GID of the host `agent-reach` group so the API process can read group-readable files. The worker service uses `UMask=0027`; keep the data directory group-owned by `agent-reach`, mode 0750, and the database mode 0640.

## API start

Set `AGENT_REACH_API_TOKEN` in the host environment or an operator-managed environment file outside the repository. Also set `AGENT_REACH_API_GID` to the numeric GID of the host `agent-reach` group. Use a long random token and restrictive file permissions. Set `AGENT_REACH_DATA_DIR=/var/lib/agent-reach`.

From the repository root:

```bash
docker compose -f deploy/docker-compose.yml config
docker compose -f deploy/docker-compose.yml build
docker compose -f deploy/docker-compose.yml up -d
```

The API is available only on loopback. Access it remotely through an SSH tunnel, for example `ssh -L 8080:127.0.0.1:8080 user@vps`. Do not open port 8080 directly to the internet.

## Worker schedule

Review `/etc/agent-reach/sources.json` before enabling `agent-reach-worker.timer`. The default example performs a public GitHub repository search every six hours. Keep frequency low and respect upstream rate limits. The worker uses the public unauthenticated GitHub API backend and does not reuse `gh` credentials.

## Operations

- Check API health: `curl http://127.0.0.1:8080/health`.
- Query records with a Bearer token at `/v1/items`; list sources at `/v1/sources`; inspect jobs at `/v1/jobs`.
- Review worker logs with `journalctl -u agent-reach-worker.service`.
- Back up SQLite using the provided backup script while the database is quiescent or via SQLite's online backup API.
- Keep logs bounded and retain only the minimum useful source extract. Do not store complete copyrighted articles or video transcripts.
- Rotate the API token by updating the external environment and restarting the API container.

## Security boundary

The API only reads stored records. The worker can invoke only configured Agent Reach channel/action pairs. The worker does not expose a shell endpoint, arbitrary URL fetch, browser session import, authenticated channel, broker credential, MT5 endpoint, or order execution capability. Do not connect this service to the existing `proxy_server.py` or `LLM_Advisor.mq5` path.

VPS deployment is not automatic. It requires operator-provisioned server access and a separate deployment review.

## Restore procedure

1. Stop the API container and disable the worker timer so no process is writing to SQLite.
2. Select a known backup file and verify it with `python3 -c 'import sqlite3,sys; c=sqlite3.connect(sys.argv[1]); print(c.execute("PRAGMA integrity_check").fetchone()[0])' <backup>`; expected output is `ok`.
3. Preserve the current database as a separate dated file before replacing it.
4. Copy the selected backup to `/var/lib/agent-reach/research.sqlite3`, set owner/group to the `agent-reach` service account/group, directory mode to 0750 and database mode to 0640.
5. Re-enable the worker timer and start the API container. Confirm `/health` reports database availability and inspect `/v1/jobs` for the last completed collection.

Worker logs are written to systemd journal. Configure host `systemd-journald` retention (for example `SystemMaxUse` and `MaxRetentionSec`) according to the VPS disk budget; do not write unbounded logs into the repository or container layer.
