.PHONY: install check test lint fmt types

UV_LINK_MODE := copy
UV_PROJECT_ENVIRONMENT ?= $(HOME)/.venvs/agentguard
export UV_LINK_MODE
export UV_PROJECT_ENVIRONMENT

install:
	uv sync --all-extras

check: lint types test

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

fmt:
	uv run ruff format .
	uv run ruff check --fix .

types:
	uv run mypy --strict src tests
