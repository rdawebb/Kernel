# Tests for Quiet Mail

This directory contains comprehensive unit tests for the Quiet Mail email client.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── test_config.py             # Configuration loading tests (5 tests)
├── test_storage.py            # Database/storage tests (21 tests)
├── test_imap_client.py        # IMAP client tests (22 tests)
├── test_smtp_client.py        # SMTP client tests (7 tests)
├── test_composer.py           # Email composer tests (13 tests)
├── test_connection.py         # Connection tests - IMAP & SMTP (10 tests)
├── test_ui.py                 # UI component tests (15 tests)
├── test_cli.py                # CLI integration tests (23 tests)
├── run_tests.py               # Legacy test runner script
└── README.md                  # This file
```

**Total: 116 comprehensive tests covering all functionality**

## Test Dependencies

The tests use the following libraries:

- `pytest` - Modern testing framework with excellent output and plugins
- `unittest.mock` - Built-in mocking library for simulating external dependencies
- `tempfile` - For creating temporary directories in storage tests
- `io.StringIO` - For capturing terminal output in CLI tests
- `rich.console` - For testing styled output rendering

## Coverage Report

The complete test suite provides comprehensive coverage of:

- **Email Operations:** IMAP connection, fetching, parsing, and deletion
- **SMTP Operations:** Connection, authentication, and email sending
- **Storage Layer:** Database operations, search, flagging, and data integrity
- **User Interface:** Display components, search views, and interaction flows
- **Command Line:** All CLI commands, error handling, and user workflows
- **Configuration:** Settings management and validation
- **Email Composition:** Message creation, formatting, and sending

All tests use mocking to avoid external dependencies (email servers, file systems) while maintaining realistic test scenarios.

## Running the Test Suite

### Using the test-suite Script (Recommended)

The project includes a comprehensive `test-suite` script with multiple execution options:

```bash
# Run all tests with standard output
./test-suite

# Run all tests with verbose output (-v)
./test-suite verbose

# Run all tests with coverage report
./test-suite coverage

# Run tests quickly (without coverage, minimal output)
./test-suite fast

# Run specific test module
./test-suite imap        # test_imap_client.py
./test-suite smtp        # test_smtp_client.py
./test-suite storage     # test_storage.py
./test-suite cli         # test_cli.py
./test-suite ui          # test_ui.py
./test-suite config      # test_config.py
./test-suite composer    # test_composer.py
./test-suite connection  # test_connection.py

# Show test count summary
./test-suite count

# Show help
./test-suite help
```

### Using pytest Directly

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest -v tests/

# Run with coverage
pytest --cov=src tests/

# Run specific test file
pytest tests/test_storage.py

# Run specific test function
pytest tests/test_cli.py::test_list_command
```

### Using Python Commands Directly

> **Note**: Replace `python` with `python3` if your system requires it (common on macOS/Linux).
> In virtual environments, `python` typically points to the correct version.

```bash
# Test which Python command works on your system:
python --version    # Should show Python 3.x
python3 --version   # Alternative on macOS/Linux

# Using pytest (recommended - provides better output)
python -m pytest tests/ -v

# Quick run with summary
python -m pytest tests/ --tb=short

# From the project root (alternative)
python -m tests.run_tests
```

The test suite automatically detects and activates virtual environments when available.

---

**Total Test Coverage: 116 tests across 8 test modules**

_This comprehensive test suite ensures reliable email client functionality with full coverage of core operations, user interface, and command-line interface._

# Run tests with coverage report

python -m pytest tests/ --cov=src/quiet_mail --cov-report=term-missing

# Or using the test suite script

./test-suite coverage

````

### Run Specific Test Patterns

```bash
# Run tests matching a pattern
python -m pytest tests/ -k "connection" -v
python -m pytest tests/ -k "smtp" -v
python -m pytest tests/ -k "attachment" -v

# Run tests excluding slow ones
python -m pytest tests/ -m "not slow" -v
````

### Debug Test Failures

```bash
# Show detailed output for failures
python -m pytest tests/ --tb=long

# Stop on first failure
python -m pytest tests/ -x

# Run with print statements visible
python -m pytest tests/ -s
```

## Test Development Guidelines

### Test Organization

- **Unit Tests**: Test individual functions in isolation
- **Integration Tests**: Test component interactions
- **Connection Tests**: Test network connectivity (mocked)
- **CLI Tests**: Test command-line interface workflows

### Mocking Strategy

- **Network Calls**: All IMAP/SMTP operations are mocked
- **File System**: Temporary files and directories used
- **Database**: In-memory SQLite databases for fast tests
- **User Input**: Rich console interactions mocked appropriately

### Test Performance

- **⚡ Fast Execution**: 116 tests complete in ~2-3 seconds
- **🔄 Parallel Ready**: Tests are isolated and can run in parallel
- **💾 Memory Efficient**: Temporary databases are small and cleaned up
- **🎯 Targeted Mocking**: Only essential components are mocked

## Continuous Integration

The test suite is designed for CI/CD environments:

```bash
# Run all tests with junit output for CI
python -m pytest tests/ --junitxml=test-results.xml

# Run with coverage for CI reporting
python -m pytest tests/ --cov=src/quiet_mail --cov-report=xml

# Performance timing for CI optimization
python -m pytest tests/ --durations=10
```

## Test File Descriptions

| File                  | Purpose               | Key Features                                |
| --------------------- | --------------------- | ------------------------------------------- |
| `test_config.py`      | Configuration loading | Environment variables, defaults, validation |
| `test_storage.py`     | Database operations   | SQLite, search, indexing, data integrity    |
| `test_imap_client.py` | Email retrieval       | IMAP operations, parsing, attachments       |
| `test_smtp_client.py` | Email sending         | SMTP operations, CC/BCC, formatting         |
| `test_composer.py`    | Email composition     | Interactive UI, validation, preview         |
| `test_connection.py`  | Network connectivity  | IMAP/SMTP connections, SSL/STARTTLS         |
| `test_ui.py`          | User interface        | Rich console, display formatting, themes    |
| `test_cli.py`         | Command line          | All CLI commands, arguments, workflows      |

## Troubleshooting

### Common Test Issues

1. **Import Errors**: Ensure you're in the project root directory
2. **Database Errors**: Tests use temporary databases that should clean up automatically
3. **Network Timeouts**: Connection tests are mocked and shouldn't make real network calls
4. **Permission Errors**: Ensure test files have write permissions

### Test Environment Setup

```bash
# Ensure all dependencies are installed
pip install -r requirements.txt
pip install pytest pytest-cov

# Run a quick test to verify setup
./test-suite count
```

### Getting Help

- Use `./test-suite help` for all testing options
- Check individual test files for specific test documentation
- Review mock configurations for network-dependent tests
- Use `pytest --tb=long` for detailed error information

- `unittest` (built-in) - Base testing framework
- `unittest.mock` (built-in) - Mocking external dependencies
- `tempfile` (built-in) - Temporary files/directories for testing
- `pathlib` (built-in) - Path handling
- `io` and `contextlib` (built-in) - Output capture for UI testing

## Recent Test Improvements

### New Features Tested (Added in 2025):

- ✅ **Email Flagging System**: Complete flag/unflag functionality
- ✅ **Advanced Search Features**: Keyword search across subject, sender, and body
- ✅ **Attachment Management**: Download, list, and search functionality
- ✅ **Email Deletion**: Local and server deletion with confirmation
- ✅ **Incremental Email Fetching**: UID-based smart refresh system
- ✅ **Enhanced Error Handling**: Comprehensive exception coverage
- ✅ **Database Management**: Improved schema and query functionality

### Test Architecture Improvements:

- ✅ **Comprehensive Mocking**: Proper isolation of external dependencies
- ✅ **Path-Accurate Patches**: Correct module patching for CLI tests
- ✅ **Resource Management**: Temporary databases and cleanup
- ✅ **Edge Case Coverage**: Non-existent data, error conditions
- ✅ **Integration Testing**: End-to-end workflow validation

### Test Coverage Areas:

1. **Configuration Management** (5 tests)

   - Environment variable loading
   - Default value handling
   - Error scenarios

2. **Database Operations** (21 tests)

   - CRUD operations
   - Search functionality
   - Attachment handling
   - UID management

3. **IMAP Client Functionality** (7 tests)

   - Connection management
   - Email processing
   - Attachment extraction

4. **User Interface Components** (15 tests)

   - Display formatting
   - Data presentation
   - Error handling

5. **Command Line Interface** (23 tests)

   - All CLI commands
   - Argument parsing
   - User interaction flows

6. **Integration Testing** (1 test)
   - Real connection validation

**Total Test Coverage: 72 comprehensive tests ensuring robust functionality across all components.**

- ✅ **Advanced Search**: Keyword search across subject, sender, and body
- ✅ **Flag-based Filtering**: Search by flagged/unflagged status
- ✅ **UI Flag Display**: Visual flag indicators (🚩) in all table views
- ✅ **CLI Command Updates**: Updated `list` command behavior (local DB default, `--refresh` for IMAP)

### Architecture Improvements:

- ✅ **DRY Principles**: Consolidated duplicate code in storage and CLI layers
- ✅ **Test Coverage**: Expanded from 40 to 58 tests (45% increase)
- ✅ **Error Handling**: Comprehensive error scenarios for all new features
- ✅ **Database Schema**: Added flagged column with proper migration testing

## Known Test Limitations

1. **IMAP Integration**: Tests mock IMAP operations for reliability and speed
2. **UI Output**: UI tests verify function calls and basic output, not pixel-perfect rendering
3. **Network Dependencies**: Connection tests may fail without internet/IMAP access
4. **Timezone Handling**: Tests assume local timezone for date/time parsing

## Adding New Tests

When adding new functionality, please:

1. **Create tests in the appropriate test file** following the module structure
2. **Follow naming conventions**: `test_*` for methods, descriptive class names
3. **Include comprehensive coverage**: Test success cases, edge cases, and error scenarios
4. **Use proper mocking**: Mock external dependencies (database, network, file system)
5. **Document test purpose**: Include docstrings explaining what each test validates
6. **Test data isolation**: Ensure tests don't interfere with each other or real data
7. **Update this README**: Add new test descriptions to the coverage section

### Example Test Structure:

```python
def test_new_feature_success_case(self):
    """Test successful execution of new feature with valid input"""
    # Setup test data
    # Execute the feature
    # Assert expected results

def test_new_feature_error_handling(self):
    """Test error handling when new feature encounters invalid input"""
    # Setup error conditions
    # Execute the feature
    # Assert proper error handling
```

## Test Data

Tests use isolated test environments to ensure:

- **Data Isolation**: Temporary databases prevent interference with real data
- **Repeatability**: Tests produce consistent results across runs
- **Mock Data**: Realistic test scenarios without external dependencies
- **Clean State**: Each test starts with a fresh, predictable environment

### Test Database Strategy:

- Each test creates its own temporary SQLite database
- Database schemas are verified to match production
- Test data includes various flag states and email types
- Cleanup is automatic via Python's `tempfile` module

## Continuous Integration

These tests are designed for CI/CD environments and provide:

- ✅ **Reliable Exit Codes**: 0 for success, 1 for failures
- ✅ **Detailed Output**: Clear failure messages for debugging
- ✅ **Fast Execution**: Complete test suite runs in ~2-3 seconds
- ✅ **No External Dependencies**: All network/database operations mocked
- ✅ **Cross-Platform Compatibility**: Works on Linux, macOS, and Windows

### CI/CD Integration Example:

```yaml
# Example GitHub Actions workflow
- name: Run Tests
  run: |
    python -m pytest tests/ -v --tb=short
    # Note: Most CI environments have 'python' pointing to Python 3

- name: Test Coverage
  run: |
    python -m pytest tests/ --cov=src --cov-report=term-missing
```

## Debugging Tests

### Common Debugging Techniques:

1. **High Verbosity Output**:

   ```bash
   python -m pytest tests/test_storage.py -v -s
   # Use python3 if your system requires it
   ```

2. **Run Individual Tests**:

   ```bash
   python -m pytest tests/test_cli.py::TestCLI::test_flag_command_flag -v
   ```

3. **Debug Mode with Print Statements**:

   ```bash
   python -m pytest tests/ -v -s --capture=no
   ```

4. **Interactive Debugging**:

   ```python
   import pdb; pdb.set_trace()  # Add to test for breakpoint
   ```

5. **Test Specific Patterns**:
   ```bash
   python -m pytest tests/ -k "flag" -v  # Run only flag-related tests
   python -m pytest tests/ -k "search" -v  # Run only search-related tests
   ```

### Debugging Test Failures:

- Check test isolation - ensure tests don't depend on each other
- Verify mock configurations match actual function signatures
- Review database state with temporary file inspection
- Use `--tb=long` for detailed traceback information

## Performance Testing

The test suite is optimized for speed:

- **⚡ Fast Execution**: 116 tests complete in ~3 seconds
- **🔄 Parallel Ready**: Tests are isolated and can run in parallel
- **💾 Memory Efficient**: Temporary databases are small and cleaned up
- **🎯 Targeted Mocking**: Only essential components are mocked

To run performance analysis:

```bash
python -m pytest tests/ --durations=10  # Show 10 slowest tests
```
