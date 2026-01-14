help:
    uv run scripts/just_help.py

install:
    uv pip install -e .

install-dev:
    uv sync --all-extras

test:
    uv run pytest tests -v

test-cov:
    uv run pytest --cov=src --cov-report=term

lint:
    uv run ruff check --fix src tests security scripts alembic

format:
    uv run ruff format src tests security scripts alembic

type:
    uv run ty check src tests security scripts alembic

clean:
    uv run scripts/clean.py

run:
    uv run scripts/run.py
