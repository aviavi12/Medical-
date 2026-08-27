# LipSight — developer commands
.DEFAULT_GOAL := help
PY ?= python3
VENV ?= .venv
PIP := $(VENV)/bin/pip
PYTHON := $(VENV)/bin/python
PYTEST := $(VENV)/bin/pytest

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z0-9_.-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}'

.PHONY: venv
venv: ## Create the Python virtualenv
	$(PY) -m venv $(VENV)

.PHONY: install
install: venv ## Install core backend + CV deps
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

.PHONY: install-ml
install-ml: ## Install heavy ML runtimes (torch, ultralytics, mediapipe, dlib, ...)
	$(PIP) install -r requirements-ml.txt

.PHONY: download-models
download-models: ## Download real model weights + GRID fixtures into ./models
	$(PYTHON) scripts/download_models.py

.PHONY: demo
demo: ## One-command real lip-reading demo on a labeled GRID clip
	$(PYTHON) scripts/demo.py $(ARGS)

.PHONY: lipread
lipread: ## Run real lip reading on your video: make lipread ARGS="--video x.mp4"
	$(PYTHON) scripts/run_real_lipreading.py $(ARGS)

.PHONY: production-test
production-test: ## Open-vocab production test: make production-test ARGS="--video x.mp4 --ground-truth '...'"
	$(PYTHON) scripts/production_lipreading_test.py $(ARGS)

.PHONY: eval-openvocab
eval-openvocab: ## Evaluate open-vocab model on evaluation/open_vocabulary (+ GRID ref)
	$(PYTHON) scripts/evaluate_open_vocabulary.py --grid-reference $(ARGS)

.PHONY: benchmark-openvocab
benchmark-openvocab: ## Benchmark open-vocab VSR: make benchmark-openvocab ARGS="--video x.mp4"
	$(PYTHON) scripts/benchmark_open_vocabulary.py $(ARGS)

.PHONY: web-install
web-install: ## Install frontend deps
	cd apps/web && npm install

.PHONY: api
api: ## Run the FastAPI backend (dev)
	$(VENV)/bin/uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000

.PHONY: web
web: ## Run the Next.js frontend (dev)
	cd apps/web && npm run dev

.PHONY: test
test: ## Run the Python test-suite
	$(PYTEST)

.PHONY: test-ml
test-ml: ## Run tests including mock-ML pipeline
	ALLOW_MOCK_INFERENCE=1 $(PYTEST) -m "ml or integration or not ml"

.PHONY: benchmark
benchmark: ## Run the pipeline benchmark (requires a video)
	$(PYTHON) scripts/benchmark_pipeline.py $(ARGS)

.PHONY: lint
lint: ## Lint Python (ruff, if installed)
	-$(VENV)/bin/ruff check .

.PHONY: db-init
db-init: ## Create database tables
	$(PYTHON) -m database.init_db

.PHONY: clean
clean: ## Remove caches
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache

.PHONY: up
up: ## docker-compose up
	docker compose up --build
