#!/usr/bin/env bash
# Full-stack smoke: the "fresh PC works" check (STATO_TECNICO §11). Brings the
# whole stack up via run-stack.sh (NO LLM: the interview is out of scope), then
# actively probes the critical paths — backend liveness, both frontends serve,
# and a real login + authenticated call — and stops the stack on exit.
#
# Expects the bootstrap default admin (a fresh/dev stack): it does NOT change
# any password, so it is safe to re-run. Override creds/ports via env if needed.
#
#   scripts/smoke-full-stack.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

BACKEND_PORT="${SMOKE_BACKEND_PORT:-8000}"
KIOSK_PORT="${SMOKE_KIOSK_PORT:-5173}"
PORTAL_PORT="${SMOKE_PORTAL_PORT:-5174}"
ADMIN_USER="${BUSSOLA_ADMIN_USERNAME:-admin}"
ADMIN_PW="${BUSSOLA_ADMIN_PASSWORD:-admin_dev_change_me}"
BACKEND="http://127.0.0.1:$BACKEND_PORT"
PYTHON="$ROOT/backend/.venv/bin/python"

pass() { printf '  OK   %s\n' "$1"; }
fail() { printf '  FAIL %s\n' "$1"; exit 1; }

# Poll an URL until it returns HTTP 200, up to N seconds.
wait_http() {
  local url="$1" what="$2" tries="${3:-40}"
  for _ in $(seq 1 "$tries"); do
    if curl -fsS -o /dev/null "$url" 2>/dev/null; then pass "$what"; return 0; fi
    sleep 1
  done
  fail "$what (timeout on $url)"
}

echo "==> Bringing up the stack (run-stack.sh, no LLM)"
bash scripts/run-stack.sh
trap 'echo "==> Stopping the stack"; bash scripts/run-stack.sh stop >/dev/null 2>&1 || true' EXIT

echo "==> Probing"
# 1. Backend liveness.
wait_http "$BACKEND/health" "backend /health"
# 2. Frontends serve (vite dev may take a few seconds to be ready).
wait_http "http://127.0.0.1:$KIOSK_PORT" "kiosk serves ($KIOSK_PORT)"
wait_http "http://127.0.0.1:$PORTAL_PORT" "operator portal serves ($PORTAL_PORT)"

# 3. Functional auth probe: real login (does NOT change the password) + one
#    authenticated call. Proves app + DB + auth are wired end to end.
LOGIN="$(curl -fsS -X POST "$BACKEND/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"username\":\"$ADMIN_USER\",\"password\":\"$ADMIN_PW\"}")" \
  || fail "login request"
TOKEN="$(printf '%s' "$LOGIN" | "$PYTHON" -c 'import sys, json; print(json.load(sys.stdin)["token"])')" \
  || fail "login returned no token (is this a fresh stack with the default admin?)"
pass "login as $ADMIN_USER"
curl -fsS -o /dev/null "$BACKEND/auth/me" -H "Authorization: Bearer $TOKEN" \
  || fail "authenticated GET /me"
pass "authenticated GET /me"

echo "==> SMOKE OK — stack comes up and the critical paths work."
