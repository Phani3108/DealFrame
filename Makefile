.PHONY: dev install install-audio install-vision db-up db-down \
        format lint test process

# ── Development ───────────────────────────────────────────────────

dev:
	uvicorn temporalos.api.main:app --reload --port 8000

install:
	pip install -e ".[dev]"

install-audio:
	pip install -e ".[audio,dev]"

install-vision:
	pip install -e ".[audio,vision,dev]"

# ── Environment ───────────────────────────────────────────────────

env:
	@if [ -f .env ]; then echo ".env already exists — skipping"; \
	else cp .env.example .env && echo "Created .env — fill in your API keys"; fi

# ── Database ──────────────────────────────────────────────────────

db-up:
	docker compose up -d postgres
	@echo "Waiting for postgres…" && sleep 2

db-down:
	docker compose down

db-reset:
	docker compose down -v && docker compose up -d postgres

# ── Code quality ──────────────────────────────────────────────────

format:
	ruff format temporalos/ tests/ evals/
	ruff check --fix temporalos/ tests/ evals/

lint:
	ruff check temporalos/ tests/ evals/
	mypy temporalos/

test:
	pytest tests/unit/ -v --cov=temporalos --cov-report=term-missing

test-e2e:
	pytest tests/e2e/ -v -s

test-all:
	pytest tests/ -v -s --cov=temporalos --cov-report=term-missing

# ── Pipeline ──────────────────────────────────────────────────────
# Usage: make process VIDEO=path/to/call.mp4

process:
	@if [ -z "$(VIDEO)" ]; then \
		echo "Usage: make process VIDEO=path/to/video.mp4"; exit 1; fi
	@JOB=$$(curl -sS -X POST http://localhost:8000/api/v1/process \
		-F "file=@$(VIDEO)" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])"); \
	echo "Job submitted: $$JOB"; \
	echo "Poll: curl http://localhost:8000/api/v1/jobs/$$JOB"
