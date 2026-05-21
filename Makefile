.PHONY: help install lint format test run consume produce-sample run-batch docker-up docker-down clean

PYTHON := python3
VENV := .venv

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install dependencies
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e ".[dev]"

lint:
	$(VENV)/bin/ruff check src tests

format:
	$(VENV)/bin/black src tests
	$(VENV)/bin/ruff check --fix src tests

test:
	$(VENV)/bin/pytest -v

run:  ## Demo against sample data (no Kafka required)
	$(VENV)/bin/python -m commerce_analytics.main demo

consume:  ## Run the speed-layer Kafka consumer
	$(VENV)/bin/python -m commerce_analytics.main consume

produce-sample:  ## Push sample events to Kafka topics
	$(VENV)/bin/python -m commerce_analytics.main produce-sample

run-batch:  ## Run the batch enrichment pipeline (CLV, funnels)
	$(VENV)/bin/python -m commerce_analytics.main batch

docker-up:
	docker compose up -d

docker-down:
	docker compose down -v

clean:
	rm -rf build dist *.egg-info .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -type d -name "__pycache__" -exec rm -rf {} +
