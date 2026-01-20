# Install in editable mode
install:
    uv pip install -e .

# Install development dependencies
install-dev:
    uv sync --all-extras

# Run all tests
test:
    uv run pytest tests -v

# Run all tests with coverage
test-cov:
    uv run pytest --cov=src --cov-report=term

# Lint code
lint:
    uv run ruff check --fix src tests security scripts alembic

# Format code
format:
    uv run ruff format src tests security scripts alembic

# Type check
type:
    uv run ty check src tests security scripts alembic

# Clean build artifacts
clean:
    uv run scripts/clean.py

# Run the application
run:
    uv run scripts/run.py
