#!/usr/bin/env bash
set -euo pipefail

# Run on a fresh Ubuntu LTS host as root.
# This script provisions the research-only Agent Reach runtime.
# It does not provision broker/MT5 access and does not expose the API publicly.

APP_DIR=/opt/agent-reach/app
VENV_DIR=/opt/agent-reach/venv
DATA_DIR=/var/lib/agent-reach
CONFIG_DIR=/etc/agent-reach
REPO_URL="${REPO_URL:-https://github.com/starasen1-coder/super-duper-octo-happiness.git}"
BRANCH="${BRANCH:-agent-reach-setup}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run as root." >&2
  exit 1
fi

apt-get update
apt-get install -y ca-certificates curl git python3 python3-venv python3-pip sqlite3

if ! command -v docker >/dev/null 2>&1; then
  apt-get install -y docker.io docker-compose-plugin
fi
systemctl enable --now docker

if ! getent group agent-reach >/dev/null; then
  groupadd --system agent-reach
fi
if ! id agent-reach >/dev/null 2>&1; then
  useradd --system --gid agent-reach --home-dir /home/agent-reach --create-home --shell /usr/sbin/nologin agent-reach
fi

install -d -o agent-reach -g agent-reach -m 0750 "$APP_DIR" "$VENV_DIR" "$DATA_DIR" "$CONFIG_DIR"

if [[ ! -d "$APP_DIR/.git" ]]; then
  git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$APP_DIR"
else
  git -C "$APP_DIR" fetch --prune origin "$BRANCH"
  git -C "$APP_DIR" checkout "$BRANCH"
  git -C "$APP_DIR" reset --hard "origin/$BRANCH"
fi
chown -R agent-reach:agent-reach "$APP_DIR"

sudo -u agent-reach python3 -m venv "$VENV_DIR"
sudo -u agent-reach "$VENV_DIR/bin/python" -m pip install --upgrade pip
sudo -u agent-reach "$VENV_DIR/bin/pip" install -r "$APP_DIR/agent-reach/requirements-api.txt"
curl --fail --location --silent --show-error \
  https://github.com/Panniantong/Agent-Reach/releases/download/v1.6.1/agent_reach-1.6.1-py3-none-any.whl \
  --output /tmp/agent_reach-1.6.1-py3-none-any.whl
echo "6a1085cae53118c5f1271ab24041e55ec17c509932612b919208f04d10183acb  /tmp/agent_reach-1.6.1-py3-none-any.whl" | sha256sum --check -
sudo -u agent-reach "$VENV_DIR/bin/pip" install /tmp/agent_reach-1.6.1-py3-none-any.whl
rm -f /tmp/agent_reach-1.6.1-py3-none-any.whl

if [[ ! -f "$CONFIG_DIR/sources.json" ]]; then
  install -o agent-reach -g agent-reach -m 0640     "$APP_DIR/agent-reach/config/sources.example.json"     "$CONFIG_DIR/sources.json"
fi

install -o root -g root -m 0644   "$APP_DIR/deploy/systemd/agent-reach-worker.service"   /etc/systemd/system/agent-reach-worker.service
install -o root -g root -m 0644   "$APP_DIR/deploy/systemd/agent-reach-worker.timer"   /etc/systemd/system/agent-reach-worker.timer

systemctl daemon-reload
systemctl enable --now agent-reach-worker.timer

echo
echo "Host preparation complete."
echo "Next: install the pinned Agent Reach v1.6.1 artifact, verify its SHA-256, configure /etc/agent-reach/sources.json, set AGENT_REACH_API_TOKEN and AGENT_REACH_API_GID outside the repository, then start deploy/docker-compose.yml."
