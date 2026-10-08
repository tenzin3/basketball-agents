#!/usr/bin/env bash
# Start everything HoopCouncil needs in one terminal: database, (local model), API and website.
# Ctrl-C stops the API, website and any Ollama this script started. The database keeps running in Docker.
set -u
cd "$(dirname "$0")/.."

# Stop every child process when this script exits or you press Ctrl-C.
trap 'trap - EXIT INT TERM; echo; echo "Stopping..."; kill 0 2>/dev/null' EXIT INT TERM

# Line-buffered sed: BSD (macOS) uses -l, GNU uses -u.
if sed -l q </dev/null >/dev/null 2>&1; then SED="sed -l"; else SED="sed -u"; fi
tag() { $SED "s/^/[$1] /"; }

provider=$(grep -E '^HOOP_LLM_PROVIDER=' .env 2>/dev/null | tail -1 | cut -d= -f2 | tr -d '"'"'"' ')
provider=${provider:-anthropic}

# 1. Database
if command -v docker >/dev/null 2>&1; then
  echo "[db] starting PostgreSQL..."
  docker compose up -d db >/dev/null || { echo "[db] Docker failed. Is Docker Desktop running?"; exit 1; }
  for _ in $(seq 1 30); do
    docker compose exec -T db pg_isready -U hoop >/dev/null 2>&1 && break
    sleep 1
  done
  echo "[db] ready"
else
  echo "[db] docker not found; assuming PostgreSQL is already running at DATABASE_URL"
fi

# 2. Local model (only when .env uses the local provider and Ollama isn't already running)
if [ "$provider" = "local" ]; then
  if curl -s http://127.0.0.1:11434 >/dev/null 2>&1; then
    echo "[ollama] already running"
  elif command -v ollama >/dev/null 2>&1; then
    OLLAMA_CONTEXT_LENGTH=${OLLAMA_CONTEXT_LENGTH:-16384} ollama serve 2>&1 | tag ollama &
  else
    echo "[ollama] HOOP_LLM_PROVIDER=local but ollama is not installed"
  fi
fi

# 3. API and 4. website
make -s api 2>&1 | tag api &
make -s web 2>&1 | tag web &

echo "Starting... open http://localhost:3000 once [web] says Ready. Press Ctrl-C to stop."
wait
