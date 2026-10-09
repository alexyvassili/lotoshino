.DEFAULT_GOAL := help

HOST ?= 127.0.0.1
PORT ?= 8000

.PHONY: help install migrations migrate run run-async check lint format test

help:
	@echo "make install     - Install dependencies from poetry.lock"
	@echo "make migrations  - Make migrations"
	@echo "make migrate     - Apply migrations"
	@echo "make run         - Run ASGI development server with autoreload"
	@echo "make run-async   - Alias for make run"
	@echo "make check       - Run all checks"
	@echo "make lint        - Run Ruff"
	@echo "make format      - Format and autofix code"
	@echo "make test        - Run Django tests"

install:
	poetry install

migrations:
	poetry run python manage.py makemigrations

migrate:
	poetry run python manage.py migrate

run:
	poetry run python -m uvicorn lotoshino.asgi:application --reload --host $(HOST) --port $(PORT)

run-async: run

lint:
	poetry run ruff check .
	poetry run ruff format --check .

format:
	poetry run ruff check --fix --exit-zero .
	poetry run ruff format .

check: lint
	poetry run python manage.py check
	poetry run python manage.py makemigrations --check --dry-run

test:
	poetry run python manage.py test
