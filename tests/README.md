# Test Suite Documentation

## Overview

This is a comprehensive test suite for the Kernel email client built with **pytest**, providing extensive coverage of all major functionality with clean, maintainable code patterns.

### Key Statistics

- **93 test methods** across 8 test modules
- **2,059 lines** of well-organized test code
- **40+ test classes** organized by functionality
- **Modern pytest patterns** with fixtures and helpers

## Quick Start

### Using the Test-Suite Script (Recommended)

The `test-suite` script at the project root provides a convenient way to run tests with various options:

```bash
# Run all tests
./test-suite

# Run with verbose output
./test-suite verbose

# Run specific module
./test-suite storage      # Database tests
./test-suite config       # Configuration tests
./test-suite connection   # Connection tests
./test-suite imap         # IMAP tests
./test-suite smtp         # SMTP tests
./test-suite ui           # UI tests
./test-suite cli          # CLI tests
./test-suite composer     # Composer tests

# Get test statistics
./test-suite count

# Show all available options
./test-suite help
```

### Run All Tests (Python)

```bash
python tests/run_tests.py
```

### Run Specific Module (Python)

```bash
python tests/run_tests.py storage      # Database tests
python tests/run_tests.py config       # Configuration tests
python tests/run_tests.py connection   # Connection tests
python tests/run_tests.py imap         # IMAP tests
python tests/run_tests.py smtp         # SMTP tests
python tests/run_tests.py ui           # UI tests
python tests/run_tests.py cli          # CLI tests
python tests/run_tests.py composer     # Composer tests
```

### Verbose Output & Coverage (Python)

```bash
python tests/run_tests.py -v           # Verbose
python tests/run_tests.py --cov        # With coverage report
```

## The test-suite Script

The `test-suite` bash script (located at the project root) provides a user-friendly interface to run tests with colored output and helpful information. It's the recommended way to run tests.

### Making the Script Executable

```bash
chmod +x test-suite
```

### Available Commands

#### Run All Tests (Default)

```bash
./test-suite              # Run complete test suite (93 tests)
./test-suite all          # Explicit 'all' command
```

#### Run with Verbose Output

```bash
./test-suite verbose      # Show detailed test names and results
./test-suite -v           # Short option
```

#### Run Tests by Module

```bash
./test-suite storage      # Database tests (11 tests)
./test-suite config       # Configuration tests (14 tests)
./test-suite connection   # Connection tests (15 tests)
./test-suite imap         # IMAP client tests (8 tests)
./test-suite smtp         # SMTP client tests (7 tests)
./test-suite ui           # UI component tests (18 tests)
./test-suite composer     # Email composer tests (12 tests)
./test-suite cli          # CLI tests (8 tests)
```

#### Get Test Statistics

```bash
./test-suite count        # Display test count breakdown by file
```

#### Run Unit Tests Only

```bash
./test-suite unit         # Run unit tests (exclude integration tests)
```

#### Show Help

```bash
./test-suite help         # Display all available commands
./test-suite -h           # Short option
./test-suite --help       # Long option
```

### Script Features

- **Colored Output**: Uses colors to make output easy to read

  - 🔵 Blue: Headers and information
  - 🟡 Yellow: Warnings and running tests
  - 🟢 Green: Successful results
  - 🔴 Red: Errors and failures

- **Virtual Environment Support**: Automatically activates `.venv` if it exists

- **Error Handling**: Exits on any test failure for CI/CD integration

- **Test Counting**: Shows breakdown of test counts per file

### Example Workflow

```bash
# 1. Make script executable (first time only)
chmod +x test-suite

# 2. Run all tests quickly
./test-suite

# 3. Run specific module to debug
./test-suite storage

# 4. Run with verbose output for details
./test-suite verbose

# 5. Check test statistics
./test-suite count
```

## Architecture

### Infrastructure Files

#### `conftest.py` (132 lines)

Central pytest configuration providing shared fixtures:

- **`temp_db`**: Temporary SQLite database for test isolation
- **`mock_config`**: Test configuration with IMAP/SMTP settings
- **`test_email`**: Single sample email fixture
- **`test_emails`**: List of sample emails fixture
- **`mock_imap_connection`**: Pre-configured IMAP mock
- **`mock_smtp_connection`**: Pre-configured SMTP mock
- **`clear_env_vars`**: Autouse fixture for automatic environment cleanup

#### `test_helpers.py` (167 lines)

Reusable helper classes eliminating duplication:

- **`DatabaseTestHelper`**: Email mock creation methods
- **`IMAPTestHelper`**: IMAP mock configuration
- **`SMTPTestHelper`**: SMTP mock configuration
- **`ConfigTestHelper`**: Configuration creation utilities
- **`ConsoleTestHelper`**: Console output capture
- **`MockBuilder`**: Fluent builder pattern for complex mocks

#### `run_tests.py` (68 lines)

Flexible pytest runner script with CLI options for running tests by module.

### Test Modules

| Module                  | Lines | Tests | Coverage                                    |
| ----------------------- | ----- | ----- | ------------------------------------------- |
| **test_storage.py**     | 180   | 11    | Database CRUD, search, flagging, backup     |
| **test_config.py**      | 195   | 14    | Configuration loading, validation, env vars |
| **test_connection.py**  | 251   | 15    | IMAP/SMTP connections, authentication       |
| **test_imap_client.py** | 185   | 8     | Email fetching, parsing, attachments        |
| **test_smtp_client.py** | 151   | 7     | Email sending, recipients, headers          |
| **test_ui.py**          | 280   | 18    | Display components, formatting              |
| **test_cli.py**         | 109   | 8     | Command dispatching, routing                |
| **test_composer.py**    | 231   | 12    | Email composition, validation               |

## Test Organization

### Class-Based Grouping

Tests are organized into logical classes grouping related functionality:

```python
class TestDatabaseManagement:
    def test_initialize_db_creates_tables(self): ...
    def test_get_db_connection(self): ...

class TestEmailCRUDOperations:
    def test_save_email_to_inbox(self): ...
    def test_delete_email_from_table(self): ...
```

### Naming Conventions

- **Test files**: `test_<module>.py`
- **Test classes**: `Test<Functionality>`
- **Test methods**: `test_<specific_scenario>`

## Using Fixtures

### Example: Database Testing

```python
def test_save_email(self, temp_db, mock_config):
    """Fixtures automatically inject dependencies"""
    with patch('src.core.db_manager.DatabaseManager.get_db_path',
               return_value=temp_db):
        storage_api.initialize_db()
        email = DatabaseTestHelper.create_mock_email()
        storage_api.save_email_to_table('inbox', email)
```

### Available Fixtures

```python
# Database isolation
def test_something(temp_db):
    pass

# Test configuration
def test_something(mock_config):
    pass

# Sample data
def test_something(test_email, test_emails):
    pass

# Pre-configured mocks
def test_something(mock_imap_connection, mock_smtp_connection):
    pass

# Automatic cleanup (no parameters needed)
# clear_env_vars fixture runs automatically
```

## Using Test Helpers

### Create Mock Emails

```python
from test_helpers import DatabaseTestHelper

# Single email
email = DatabaseTestHelper.create_mock_email(
    uid='test123',
    subject='Test Subject',
    sender='test@example.com',
    flagged=True
)

# Multiple emails
emails = DatabaseTestHelper.create_mock_emails(
    count=5,
    sender='bulk@example.com'
)
```

### Create Test Configuration

```python
from test_helpers import ConfigTestHelper

config = ConfigTestHelper.create_test_config(
    imap_host='imap.example.com',
    imap_port=993,
    smtp_host='smtp.example.com'
)
```

### Create Pre-Configured Mocks

```python
from test_helpers import IMAPTestHelper, SMTPTestHelper

mock_imap = IMAPTestHelper.create_mock_imap()
mock_smtp = SMTPTestHelper.create_mock_smtp()
```

### Capture Console Output

```python
from test_helpers import ConsoleTestHelper

with ConsoleTestHelper.capture_console_output() as output:
    print("Hello")
assert "Hello" in output.getvalue()
```

### Fluent Mock Builder

```python
from test_helpers import MockBuilder

mock = (MockBuilder()
    .with_method('fetch', return_value=[])
    .with_method('select', return_value=('OK', []))
    .build())
```

## Test Patterns

### Basic Test

```python
def test_basic_scenario(self, temp_db):
    """Tests basic happy path"""
    # Setup
    data = create_test_data()

    # Execute
    result = function_under_test(data)

    # Assert
    assert result is not None
```

### Testing with Mocks

```python
def test_with_mock(self):
    """Tests with mocking external dependencies"""
    mock = MagicMock()

    with patch('module.external_service', mock):
        result = function_using_service()

    mock.assert_called_once()
```

### Error Handling

```python
def test_error_handling(self):
    """Tests error scenarios"""
    with pytest.raises(ValueError):
        invalid_input_function()
```

### Parametrized Tests (Extensible)

```python
@pytest.mark.parametrize('input,expected', [
    ('a', 1),
    ('b', 2),
])
def test_parametrized(self, input, expected):
    assert process(input) == expected
```

## Modules Tested

### ✅ Database Operations (`src.core.storage_api`)

- Database initialization
- CRUD operations (Save, Get, Delete)
- Email search
- Flagging/unflagging
- Moving between tables
- Backup & export

### ✅ Configuration (`src.utils.config_manager`)

- Configuration loading
- Default values
- Validation
- Environment variables
- Database paths
- SSL/TLS settings

### ✅ Email Connections (`src.core.imap_client`, `src.core.smtp_client`)

- IMAP/SMTP authentication
- Connection setup
- Context managers
- Error handling

### ✅ IMAP Operations (`src.core.imap_client`)

- Header decoding
- Filename decoding
- Date parsing
- Email fetching
- Attachment extraction
- Email deletion

### ✅ SMTP Operations (`src.core.smtp_client`)

- Email sending
- Recipient handling (To/CC/BCC)
- Custom headers
- Authentication
- Error scenarios

### ✅ UI Components (`src.ui`)

- Inbox display
- Email viewer
- Search results
- Data formatting
- Error handling

### ✅ CLI (`src.cli`)

- Command dispatching
- Argument parsing
- Async handling

### ✅ Email Composer (`src.ui.composer`)

- Composition workflow
- Validation
- Send/draft/schedule

### ❌ Excluded

- `src.core.summariser` - Not integrated yet (per requirements)

## Best Practices

### Do's

✅ Use fixtures for common setup
✅ Use helpers for mock creation
✅ Group related tests in classes
✅ Clear descriptive test names
✅ Test both success and failure paths
✅ Isolate units under test with mocking
✅ Keep tests focused and independent

### Don'ts

❌ Don't use hardcoded paths
❌ Don't rely on environment variables (use fixtures)
❌ Don't have tests depend on each other
❌ Don't create actual files/databases (use temp_db)
❌ Don't mix multiple concerns in one test
❌ Don't forget to mock external services

## Debugging Tests

### Verbose Output

```bash
python tests/run_tests.py -v          # Shows test names
python tests/run_tests.py -vv         # Very verbose with prints
```

### Run Specific Tests

```bash
pytest tests/test_storage.py::TestDatabaseManagement
pytest tests/test_storage.py::TestDatabaseManagement::test_initialize_db_creates_tables
```

### Stop on First Failure

```bash
pytest tests/ -x
```

### Run Only Failed Tests

```bash
pytest tests/ --lf
```

### Show Print Output

```bash
pytest tests/ -s
```

### Debug with Pdb

```python
def test_something():
    import pdb; pdb.set_trace()
    result = function_under_test()
```

## Adding New Tests

### Template

```python
"""
Test module for [component]

Tests cover:
- [feature 1]
- [feature 2]
"""
import pytest
from unittest.mock import patch

from src.module import function_under_test
from .test_helpers import AppropriateHelper


class TestComponentFeature:
    """Tests for [specific feature]"""

    def test_basic_scenario(self, fixture_name):
        """Test description"""
        # Setup
        test_data = AppropriateHelper.create_test_data()

        # Execute
        result = function_under_test(test_data)

        # Assert
        assert result is not None
```

### Checklist

- [ ] Test in appropriate `test_*.py` file
- [ ] Test class groups related tests
- [ ] Test method name describes scenario
- [ ] Uses fixtures from `conftest.py`
- [ ] Uses helpers from `test_helpers.py`
- [ ] Includes docstring
- [ ] Mocks external dependencies
- [ ] Tests success and failure paths
- [ ] No hardcoded paths/env vars
- [ ] Automatic cleanup via fixtures

## Coverage Map

```
src/
├── core/
│   ├── storage_api.py          ✅ test_storage.py (11 tests)
│   ├── imap_client.py          ✅ test_imap_client.py (8 tests)
│   ├── smtp_client.py          ✅ test_smtp_client.py (7 tests)
│   ├── db_manager.py           ✅ test_storage.py (11 tests)
│   ├── email_operations.py     ✅ test_storage.py (11 tests)
│   ├── email_search.py         ✅ test_storage.py (11 tests)
│   └── summariser.py           ❌ Not integrated yet
├── cli/
│   └── cli.py                  ✅ test_cli.py (8 tests)
├── ui/
│   ├── composer.py             ✅ test_composer.py (12 tests)
│   ├── inbox_viewer.py         ✅ test_ui.py (18 tests)
│   ├── email_viewer.py         ✅ test_ui.py (18 tests)
│   └── search_viewer.py        ✅ test_ui.py (18 tests)
└── utils/
    ├── config_manager.py       ✅ test_config.py (14 tests)
    └── scheduler.py            (Tested via test_send_later.py legacy)

Connection Testing:
├── IMAP                        ✅ test_connection.py (15 tests)
├── SMTP SSL                    ✅ test_connection.py (15 tests)
└── SMTP STARTTLS              ✅ test_connection.py (15 tests)
```

## Files Reference

### Main Test Files

- `conftest.py` - Pytest configuration and shared fixtures
- `test_helpers.py` - Reusable helper classes
- `run_tests.py` - Test runner script
- `test_storage.py` - Database operation tests
- `test_config.py` - Configuration tests
- `test_connection.py` - Connection tests
- `test_imap_client.py` - IMAP operation tests
- `test_smtp_client.py` - SMTP operation tests
- `test_ui.py` - UI component tests
- `test_cli.py` - CLI command tests
- `test_composer.py` - Email composer tests

### Documentation

- `README.md` - This file
- `QUICK_REFERENCE.md` - Quick developer reference
- `TESTING_SUMMARY.md` - Complete refactoring summary

## Statistics

- **Total Lines**: 2,059 (test code + infrastructure)
- **Test Methods**: 93 across 8 modules
- **Test Classes**: 40+
- **Framework**: pytest (modern, flexible, extensible)
- **Python Version**: 3.13+

## Performance

Tests run quickly due to:

- Isolated database usage (temp_db per test)
- Mocking all external services
- Automatic cleanup (no test pollution)
- Focused test scope

Typical full suite run: < 10 seconds

## Continuous Integration

This test suite is ready for CI/CD:

```bash
# Standard CI command
python tests/run_tests.py

# With coverage
python tests/run_tests.py --cov

# Or direct pytest
pytest tests/ -v --cov
```

## Troubleshooting

### "Module not found" errors

**Solution**: Run tests from project root with `python tests/run_tests.py`

### Database locked errors

**Solution**: `temp_db` fixture prevents this - ensure tests use the fixture

### Environment variable issues

**Solution**: `clear_env_vars` autouse fixture handles cleanup automatically

### Mock not being called

**Solution**: Check patch path matches the import statement in the module

### Test passes locally but fails in CI

**Solution**: Check for environment dependencies, mock external services

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [unittest.mock Documentation](https://docs.python.org/3/library/unittest.mock.html)
- See `QUICK_REFERENCE.md` for developer cheat sheet
- See `TESTING_SUMMARY.md` for detailed refactoring information

## Contributing

When adding tests:

1. Follow existing patterns in similar test modules
2. Use fixtures and helpers to reduce duplication
3. Group tests logically in classes
4. Write clear docstrings
5. Mock external dependencies
6. Test both success and failure scenarios

---

**Last Updated**: After comprehensive test suite refactoring
**Framework**: pytest
**Status**: ✅ Complete and Verified
**Coverage**: ~115 tests across all major modules (except summariser)
