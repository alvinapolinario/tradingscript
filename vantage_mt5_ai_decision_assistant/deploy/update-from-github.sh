#!/usr/bin/env bash
# Update Vantage API on Linux VPS from GitHub, then rebuild Docker.
# Safe: keeps local .env; signal ledger volume is preserved by compose.
#
# This VPS layout:
#   /var/www/tradingscript/                          # git root
#   /var/www/tradingscript/vantage_mt5_ai_decision_assistant/
#
# Run from anywhere:
#   bash /var/www/tradingscript/vantage_mt5_ai_decision_assistant/deploy/update-from-github.sh

set -euo pipefail

BRANCH="${BRANCH:-main}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "==> App dir: ${APP_DIR}"
cd "${APP_DIR}"

if [[ ! -f docker-compose.yml ]]; then
  echo "ERROR: docker-compose.yml not found in ${APP_DIR}" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "ERROR: missing .env — copy from .env.docker.example and set secrets first." >&2
  exit 1
fi

REPO_ROOT="$(cd "${APP_DIR}/.." && pwd)"
if [[ -d "${REPO_ROOT}/.git" ]]; then
  echo "==> Pulling ${BRANCH} from GitHub…"
  git -C "${REPO_ROOT}" fetch origin "${BRANCH}"
  git -C "${REPO_ROOT}" checkout "${BRANCH}"
  git -C "${REPO_ROOT}" pull --ff-only origin "${BRANCH}"
  echo "==> HEAD: $(git -C "${REPO_ROOT}" rev-parse --short HEAD)"
else
  echo "WARN: ${REPO_ROOT} is not a git checkout — skipping pull (building current files)."
fi

echo "==> Rebuilding and restarting container…"
docker compose up -d --build

echo "==> Waiting for health…"
ok=0
for i in $(seq 1 30); do
  if curl -fsS "http://127.0.0.1:8000/health" >/dev/null 2>&1; then
    ok=1
    break
  fi
  sleep 2
done

if [[ "${ok}" -ne 1 ]]; then
  echo "ERROR: health check failed. Recent logs:" >&2
  docker compose logs --tail=80 vantage-api >&2 || true
  exit 1
fi

echo "==> Healthy. Smoke checks:"
curl -fsS "http://127.0.0.1:8000/health" || true
echo
echo "  Analyzer:  http://187.77.142.118:8000/analyzer"
echo "  Signals:   http://187.77.142.118:8000/signals"
echo "  Monitor:   http://187.77.142.118:8000/monitor"
echo "==> Done."
