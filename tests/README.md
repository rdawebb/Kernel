# Tests for Quiet Mail

This directory contains comprehensive unit tests for the Quiet Mail email client.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── test_config.py             # Configuration loading tests
├── test_storage.py            # Database/storage tests
├── test_imap_client.py        # IMAP client tests
├── test_ui.py                 # UI component tests
├── test_cli.py                # CLI integration tests
├── run_tests.py               # Test runner script
└── README.md                  # This file
```

## Running Tests

### Run All Tests

```bash
# From the project root
python -m tests.run_tests

# Or from the tests directory
python run_tests.py
```

### Run Specific Test Modules

```bash
# Run only configuration tests
python run_tests.py config

# Run only storage tests
python run_tests.py storage

# Run only IMAP tests
python run_tests.py imap_client

# Run only UI tests
python run_tests.py ui

# Run only CLI tests
python run_tests.py cli
```

### Run Individual Test Files

```bash
# Run specific test file directly
python -m unittest tests.test_config
python -m unittest tests.test_storage
```

## Test Coverage

### Configuration Tests (`test_config.py`)

- ✅ Valid environment variable loading
- ✅ Missing required variables handling
- ✅ Invalid port number handling
- ✅ Default value assignment
- ✅ SSL flag parsing variations

### Storage Tests (`test_storage.py`)

- ✅ Database connection creation
- ✅ Database initialization
- ✅ Email metadata saving
- ✅ Email body saving
- ✅ Inbox retrieval with limits
- ✅ Individual email retrieval
- ✅ Error handling for database operations
- ✅ Temporary database for testing

### IMAP Client Tests (`test_imap_client.py`)

- ✅ IMAP connection success/failure
- ✅ Login authentication testing
- ✅ Mock email fetching
- ✅ Limit parameter handling
- ✅ Exception handling

### UI Tests (`test_ui.py`)

- ✅ Inbox table display
- ✅ Email detail display
- ✅ Handling missing email fields
- ✅ Rich formatting integration
- ✅ Data integrity verification

### CLI Tests (`test_cli.py`)

- ✅ List command functionality
- ✅ View command functionality
- ✅ Command-line argument parsing
- ✅ Error handling for various failure scenarios
- ✅ Database initialization testing

## Test Dependencies

The tests use the following libraries:

- `unittest` (built-in) - Main testing framework
- `unittest.mock` (built-in) - Mocking external dependencies
- `tempfile` (built-in) - Temporary files/directories for testing
- `pathlib` (built-in) - Path handling

## Known Test Limitations

1. **IMAP Integration**: Tests currently mock IMAP operations since the current implementation uses hardcoded test data
2. **UI Output**: UI tests verify function calls but don't test actual visual output
3. **Storage Bug**: Tests reveal that `save_email_body()` function has a bug - it expects a `uid` that isn't saved by `save_email_metadata()`

## Adding New Tests

When adding new functionality, please:

1. Create tests in the appropriate test file
2. Follow the existing naming convention (`test_*`)
3. Use descriptive test method names
4. Include docstrings explaining what each test does
5. Mock external dependencies (database, network, etc.)
6. Test both success and failure scenarios

## Test Data

Tests use temporary databases and mock data to ensure:

- Tests don't interfere with real data
- Tests are repeatable and isolated
- No external dependencies are required

## Continuous Integration

These tests are designed to be run in CI/CD environments and will:

- Exit with code 0 on success
- Exit with code 1 on any failures
- Provide detailed output for debugging

## Debugging Tests

To debug failing tests:

1. Run tests with high verbosity: `python -m unittest -v tests.test_module`
2. Run individual test methods: `python -m unittest tests.test_module.TestClass.test_method`
3. Add print statements or use `pdb.set_trace()` for interactive debugging
4. Check test isolation - ensure tests don't depend on each other
