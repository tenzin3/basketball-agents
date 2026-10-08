PY ?= python3
VENV = backend/.venv
BIN = $(VENV)/bin

.PHONY: setup db pipeline test api web dev simulate report copy-db

setup:            ## create venv + install backend and frontend deps
	$(PY) -m venv $(VENV)
	$(BIN)/pip install -U pip
	$(BIN)/pip install -e "backend[dev]"
	cd frontend && npm install

db:               ## start PostgreSQL (docker)
	docker compose up -d db

pipeline:         ## scrape (rate limited, ~7 min first run) -> DB -> derive -> context cache
	cd backend && ../$(BIN)/hoop pipeline

report:           ## print data-quality reports
	cd backend && ../$(BIN)/hoop report

test:
	cd backend && ../$(BIN)/python -m pytest -q

dev:              ## database + (Ollama) + API + website in one terminal; Ctrl-C stops all
	@./scripts/dev.sh

api:
	cd backend && ../$(BIN)/hoop serve --reload

web:
	cd frontend && npm run dev

simulate:
	cd backend && ../$(BIN)/python simulate.py

copy-db:          ## copy your local database to the hosted one (Neon on Vercel): make copy-db TO="postgresql://..."
	@test -n "$(TO)" || (echo 'Usage: make copy-db TO="postgresql://user:pass@host/db?sslmode=require"' && exit 1)
	cd backend && ../$(BIN)/hoop copy-db "$(TO)"
