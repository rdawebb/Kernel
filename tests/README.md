# Tests for Quiet Mail

This directory contains comprehensive unit tests for the Quiet Mail email client.

## Test Structure

```
tests/
├── __init__.py                 # Test package initialization
├── test_config.py             # Configuration loading tests (5 tests)
├── test_storage.py            # Database/storage tests (21 tests)
├── test_imap_client.py        # IMAP client tests (7 tests)
├── test_connection.py         # IMAP connection integration test (1 test)
├── test_ui.py                 # UI component tests (15 tests)
├── test_cli.py                # CLI integration tests (23 tests)
├── run_tests.py               # Test runner script
└── README.md                  # This file
```

**Total: 72 comprehensive tests covering all functionality**

## Quick Start

### Check Your Python Command

```bash
# Test which Python command works on your system:
python --version    # Should show Python 3.x
python3 --version   # Alternative on macOS/Linux

# If python shows Python 2.x, use python3 for all commands below
```

## Running Tests

> **Note**: Replace `python` with `python3` if your system requires it (common on macOS/Linux).
> In virtual environments, `python` typically points to the correct version.

### Run All Tests (Recommended)

```bash
# Using pytest (recommended - provides better output)
python -m pytest tests/ -v

# Quick run
python -m pytest tests/ -q

# From the project root (alternative)
python -m tests.run_tests

# Or from the tests directory
python run_tests.py
```

### Run Specific Test Modules

````bash
# Run only configuration tests
python -m pytest tests/test_config.py -v

# Run only storage tests
python -m pytest tests/test_storage.py -v

# Run only IMAP tests
python -m pytest tests/test_imap_client.py -v

# Run only UI tests
python -m pytest tests/test_ui.py -v

# Run only CLI tests
python -m pytest tests/test_cli.py -v

# Run connection integration test
python -m pytest tests/test_connection.py -v
```### Run Individual Test Methods

```bash
# Run specific test file directly
python -m unittest tests.test_config.TestConfig.test_load_config_defaults
python -m unittest tests.test_storage.TestStorage.test_search_emails_by_keyword

# Run specific test class
python -m unittest tests.test_cli.TestCLI
python -m unittest tests.test_ui.TestSearchViewer

# Note: Use 'python3' instead of 'python' if required by your system
````

## Test Coverage

### Configuration Tests (`test_config.py`) - 5 tests

- ✅ Valid environment variable loading
- ✅ Missing required variables handling
- ✅ Invalid port number handling
- ✅ Default value assignment
- ✅ SSL flag parsing variations

### Storage Tests (`test_storage.py`) - 21 tests

**Core Database Operations:**

- ✅ Database connection creation
- ✅ Database initialization with flagged column
- ✅ Email metadata saving
- ✅ Email body saving
- ✅ Inbox retrieval with limits
- ✅ Individual email retrieval
- ✅ Error handling for database operations

**Email Management Features:**

- ✅ Email flagging/unflagging functionality
- ✅ Search emails by keyword (subject, sender, body)
- ✅ Search flagged emails only
- ✅ Search unflagged emails only
- ✅ Limit functionality with proper ordering
- ✅ Flagged column inclusion in all search results
- ✅ Database schema validation

**New Attachment and Deletion Features:**

- ✅ Search emails with attachments functionality
- ✅ Get highest UID for incremental email fetching
- ✅ Delete email from local database
- ✅ Handle deletion of non-existent emails gracefully

### IMAP Client Tests (`test_imap_client.py`) - 7 tests

**Connection Management:**

- ✅ IMAP connection success/failure scenarios
- ✅ Login authentication testing
- ✅ Exception handling for network errors

**Email Processing:**

- ✅ Email header decoding with encoding handling
- ✅ Attachment filename decoding
- ✅ Attachment filename extraction from emails
- ✅ Attachment file saving with duplicate handling

### Connection Tests (`test_connection.py`) - 1 test

- ✅ Integration test for IMAP server connectivity

### UI Tests (`test_ui.py`) - 15 tests

**Inbox Viewer (4 tests):**

- ✅ Inbox table display with flagged status
- ✅ Empty inbox handling
- ✅ Flagged column and emoji display
- ✅ Missing field graceful handling

**Email Viewer (4 tests):**

- ✅ Complete email detail display
- ✅ Missing body handling
- ✅ Missing field handling
- ✅ Data integrity verification

**Search Viewer (4 tests):**

- ✅ Search results display with flagged status
- ✅ Empty search results handling
- ✅ Flagged-only email display
- ✅ Unflagged-only email display

**Integration Tests (3 tests):**

- ✅ Inbox to email workflow
- ✅ Empty data handling
- ✅ Component interaction testing

### CLI Tests (`test_cli.py`) - 23 tests

**Core Commands:**

- ✅ List command default behavior (local database)
- ✅ Refresh command for fetching new emails from server
- ✅ List command with limit parameter
- ✅ View command for existing/nonexistent emails
- ✅ Configuration and IMAP error handling

**Email Management Commands:**

- ✅ Search command by keyword
- ✅ Flagged emails listing
- ✅ Unflagged emails listing
- ✅ Flag email command
- ✅ Unflag email command
- ✅ Flag command error handling (missing options, nonexistent emails)

**Attachment Management Commands:**

- ✅ Attachments command (list emails with attachments)
- ✅ List-attachments command (show attachment filenames)
- ✅ Download command with attachments validation
- ✅ Download command with all/index options

**Email Deletion Commands:**

- ✅ Delete command (local database only)
- ✅ Delete command (both local and server with --all flag)
- ✅ Delete command cancellation handling
- ✅ User confirmation workflow

**System Commands:**

- ✅ Help command functionality
- ✅ Invalid command handling
- ✅ Storage operation failure handling

## Test Dependencies

The tests use the following libraries:

- `pytest` - Modern testing framework with excellent output and plugins
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

- **⚡ Fast Execution**: 58 tests complete in ~2-3 seconds
- **🔄 Parallel Ready**: Tests are isolated and can run in parallel
- **💾 Memory Efficient**: Temporary databases are small and cleaned up
- **🎯 Targeted Mocking**: Only essential components are mocked

To run performance analysis:

```bash
python -m pytest tests/ --durations=10  # Show 10 slowest tests
```
