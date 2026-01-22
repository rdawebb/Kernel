# Install Python in editable mode
install:
    uv pip install -e .

# Build Go binary
go-build:
	cd native/go && go build -o ../build/kernel-native .

# Development mode with auto-reload (requires air)
go-dev:
	cd native/go && air

# Install Python development dependencies
py-deps:
    uv sync --all-extras

# Install Go dependencies
go-deps:
	cd native/go && go mod download

# Run all Python tests
py-test:
    uv run pytest tests -v

# Run all Go tests
go-test:
	cd native/go && go test ./...

# Run all Python tests with coverage
test-cov:
    uv run pytest --cov=src --cov-report=term

# Lint Python code
lint:
    uv run ruff check --fix src tests scripts alembic

# Format Python code
format:
    uv run ruff format src tests scripts alembic

# Type Python check
type:
    uv run ty check src tests scripts alembic

# Clean build artifacts
clean:
    uv run scripts/clean.py

# Run the server
go-run: go-build
	NATIVE_SOCKET_PATH=/tmp/kernel.sock ./native/build/kernel-native

# Run the application
run:
    uv run scripts/run.py
