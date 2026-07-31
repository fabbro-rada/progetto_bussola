#!/usr/bin/env bash
# One-command DEV stack for Bussola (STATO_TECNICO §11). Brings up Postgres,
# applies migrations, bootstraps an admin, and runs the backend API + kiosk +
# operator portal. The LLM (llama-server, GPU, ~4.7 GB on first run) is opt-in
# via --with-llm; otherwise the script checks :8080 and warns (the interview
# needs it). NOT for production (§12): localhost only, dev passwords from .env.
#
#   scripts/run-stack.sh [--with-llm]   start the stack
#   scripts/run-stack.sh stop           stop everything this script started
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_DIR="$ROOT/.run-stack"
mkdir -p "$RUN_DIR"

# Docker Compose command: prefer the v2 plugin ("docker compose"), fall back to
# the v1 standalone ("docker-compose"). Empty if neither is installed — the
# start path errors with an install hint (a bare "docker compose ..." otherwise
# fails with a cryptic "unknown shorthand flag 'd'"). Used UNQUOTED on purpose
# so the v2 form word-splits into two args.
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
else
  DC=""
fi

SERVICES="portal kiosk backend llm"  # stop order (reverse of start)

# --- stop mode -------------------------------------------------------------
if [ "${1:-}" = "stop" ]; then
  for svc in $SERVICES; do
    pidfile="$RUN_DIR/$svc.pid"
    [ -f "$pidfile" ] || continue
    pid="$(cat "$pidfile")"
    # Services are started via setsid, so pid is a process-group leader: kill
    # the whole group (negative pid) to also reap npm's vite child, etc.
    if kill -TERM -- "-$pid" 2>/dev/null; then
      echo "stopped $svc (pgid $pid)"
    elif kill -TERM "$pid" 2>/dev/null; then
      echo "stopped $svc (pid $pid)"
    fi
    rm -f "$pidfile"
  done
  [ -n "$DC" ] && $DC stop db >/dev/null 2>&1 && echo "stopped db" || true
  echo "stack stopped."
  exit 0
fi

WITH_LLM=0
[ "${1:-}" = "--with-llm" ] && WITH_LLM=1

# start a command in its own session (process-group leader) and record its pid
start_bg() {
  local name="$1"; shift
  setsid bash -c "$*" >"$RUN_DIR/$name.log" 2>&1 &
  echo $! >"$RUN_DIR/$name.pid"
}

# --- preflight: the ports we bind must be free --------------------------
port_busy() { ss -ltn 2>/dev/null | grep -q ":$1 "; }
busy=""
for p in 8000 5173 5174; do
  port_busy "$p" && busy="$busy $p"
done
if [ -n "$busy" ]; then
  echo "ERROR: port(s) already in use:$busy"
  echo "  Bussola needs 8000 (API), 5173 (kiosk), 5174 (portal) free."
  echo "  Free them (or 'scripts/run-stack.sh stop' if a prior run left processes) and retry."
  exit 1
fi

# --- .env ------------------------------------------------------------------
if [ ! -f .env ]; then
  cp .env.example .env
  echo "WARN: created .env from .env.example — dev passwords in use (change for anything real, §12)."
fi
# The kiosk device token lives in frontend/.env (VITE_KIOSK_TOKEN) and must match
# BUSSOLA_KIOSK_TOKEN here, or the kiosk shows "postazione non autorizzata".
if [ ! -f frontend/.env ]; then
  cp frontend/.env.example frontend/.env
  echo "WARN: created frontend/.env from example — kiosk dev token in use (set a real one on the locked box, §12)."
fi
be_tok="${BUSSOLA_KIOSK_TOKEN:-$(grep -E '^BUSSOLA_KIOSK_TOKEN=' .env 2>/dev/null | cut -d= -f2-)}"
fe_tok="$(grep -E '^VITE_KIOSK_TOKEN=' frontend/.env 2>/dev/null | cut -d= -f2-)"
if [ -z "$be_tok" ]; then
  echo "WARN: BUSSOLA_KIOSK_TOKEN not set (.env) — the kiosk will be 'non autorizzato'."
elif [ "$be_tok" != "$fe_tok" ]; then
  echo "WARN: BUSSOLA_KIOSK_TOKEN (.env) != VITE_KIOSK_TOKEN (frontend/.env) — the kiosk will be 'non autorizzato'."
fi

# --- 1. Postgres -----------------------------------------------------------
if [ -z "$DC" ]; then
  echo "ERROR: Docker Compose non trovato. Installa il plugin v2:"
  echo "  Ubuntu/Debian:  sudo apt-get install docker-compose-v2   (fornisce 'docker compose')"
  echo "  repo Docker:    sudo apt-get install docker-compose-plugin"
  echo "  docs:           https://docs.docker.com/compose/install/"
  exit 1
fi
echo "==> Postgres ($DC up -d db)"
$DC up -d db
printf "    waiting for Postgres"
for i in $(seq 1 30); do
  if $DC exec -T db pg_isready -U postgres >/dev/null 2>&1; then printf " ready\n"; break; fi
  printf "."; sleep 1
  if [ "$i" = 30 ]; then printf " TIMEOUT\n"; exit 1; fi
done

# --- backend venv ----------------------------------------------------------
if [ ! -d backend/.venv ]; then
  echo "ERROR: backend/.venv missing — set up the backend first: 'cd backend && uv sync --all-extras' (STATO_TECNICO §11)."
  exit 1
fi
for app in frontend operator-portal; do
  if [ ! -d "$app/node_modules" ]; then
    echo "ERROR: $app/node_modules missing — run 'npm ci' in $app/ first (STATO_TECNICO §11)."
    exit 1
  fi
done
# shellcheck disable=SC1091
source backend/.venv/bin/activate

# --- model preflight (warn, non-fatal) -------------------------------------
# en_core_web_lg is now a backend dependency, so 'uv sync' installs it; warn if
# the venv predates that. Piper voices are a separate download (not a pip pkg).
if ! python -c "import en_core_web_lg" >/dev/null 2>&1; then
  echo "WARN: spaCy model en_core_web_lg missing (PII/guardrails; the kiosk interview will error). Run: (cd backend && uv sync --all-extras)"
fi
if ! ls models/voice/*.onnx >/dev/null 2>&1; then
  echo "WARN: no Piper voices in models/voice/ — read-aloud (TTS) unavailable. Run: bash scripts/fetch-voice-models.sh"
fi

# --- 2. migrations ---------------------------------------------------------
echo "==> Applying migrations"
( cd backend && python -m bussola.data.migrate )

# --- 3. bootstrap admin (idempotent) ---------------------------------------
echo "==> Bootstrapping admin (if not present)"
: "${BUSSOLA_ADMIN_USERNAME:=admin}"
: "${BUSSOLA_ADMIN_PASSWORD:=admin_dev_change_me}"
export BUSSOLA_ADMIN_USERNAME BUSSOLA_ADMIN_PASSWORD
if ( cd backend && python -m bussola.auth.bootstrap ) 2>"$RUN_DIR/bootstrap.err"; then
  echo "    admin '$BUSSOLA_ADMIN_USERNAME' ready (must change password at first login)."
else
  # bootstrap refuses if an admin already exists — that's fine; surface anything else
  if grep -qiE "exist|already|duplicate" "$RUN_DIR/bootstrap.err"; then
    echo "    admin already exists — skipping."
  else
    echo "    bootstrap note (see $RUN_DIR/bootstrap.err):"; sed 's/^/      /' "$RUN_DIR/bootstrap.err"
  fi
fi

# --- 4. LLM (opt-in) -------------------------------------------------------
if curl -sf http://127.0.0.1:8080/health >/dev/null 2>&1; then
  echo "==> LLM already running on :8080"
elif [ "$WITH_LLM" = 1 ]; then
  echo "==> Starting LLM (llama-server) — first run downloads ~4.7 GB, uses the GPU"
  start_bg llm "cd '$ROOT' && bash scripts/serve-llm.sh"
else
  echo "==> LLM NOT running on :8080 — the interview needs it. Start it with:"
  echo "      bash scripts/serve-llm.sh        (or re-run: scripts/run-stack.sh --with-llm)"
fi

# --- 5. backend API --------------------------------------------------------
echo "==> Backend API -> http://127.0.0.1:8000"
start_bg backend "cd '$ROOT/backend' && source .venv/bin/activate && exec uvicorn bussola.api.app:create_app --factory --host 127.0.0.1 --port 8000"
printf "    waiting for backend"
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then printf " ready\n"; break; fi
  printf "."; sleep 1
  if [ "$i" = 30 ]; then printf " TIMEOUT (see %s)\n" "$RUN_DIR/backend.log"; fi
done

# --- 6. frontends ----------------------------------------------------------
echo "==> Kiosk -> http://localhost:5173"
start_bg kiosk "cd '$ROOT/frontend' && exec npm run dev"
echo "==> Operator portal -> http://localhost:5174"
start_bg portal "cd '$ROOT/operator-portal' && exec npm run dev"

cat <<INFO

Stack up.
  Kiosk (persona):    http://localhost:5173
  Portale operatore:  http://localhost:5174   (admin: $BUSSOLA_ADMIN_USERNAME)
  Backend API:        http://127.0.0.1:8000
  Logs:  $RUN_DIR/*.log
  Stop:  scripts/run-stack.sh stop
INFO
