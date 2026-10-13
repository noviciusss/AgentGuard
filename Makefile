.PHONY: install check test lint fmt types

UV_LINK_MODE := copy
UV_PROJECT_ENVIRONMENT ?= $(HOME)/.venvs/agentguard
export UV_LINK_MODE
export UV_PROJECT_ENVIRONMENT

install:
	uv sync --locked --all-extras

check: lint types test

test:
	uv run --locked --all-extras pytest

lint:
	uv run --locked --all-extras ruff check .
	uv run --locked --all-extras ruff format --check .

fmt:
	uv run --locked --all-extras ruff check --fix .
	uv run --locked --all-extras ruff format .

types:
	uv run --locked --all-extras mypy --strict packages/agentguard-core/src packages/agentguard-langgraph/src packages/agentguard-graph/src packages/agentguard-owasp/src packages/agentguard-llm-triage/src packages/agentguard-trace/src tests
