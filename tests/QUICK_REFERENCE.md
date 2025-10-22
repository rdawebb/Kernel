# Test Suite Quick Reference

## 📁 File Structure

```
tests/
├── conftest.py              # Pytest configuration & shared fixtures
├── test_helpers.py          # Reusable helper classes for tests
├── run_tests.py             # Test runner script
├── README.md                # Comprehensive documentation
├── test_storage.py          # Database operations (180 lines)
├── test_config.py           # Configuration management (195 lines)
├── test_connection.py       # Email server connections (251 lines)
├── test_imap_client.py      # IMAP operations (185 lines)
├── test_smtp_client.py      # SMTP operations (151 lines)
├── test_ui.py               # UI components (280 lines)
├── test_cli.py              # CLI commands (109 lines)
└── test_composer.py         # Email composer (231 lines)
```

## 🚀 Running Tests

### Using test-suite Script (Recommended)

```bash
# Make script executable (first time only)
chmod +x test-suite

# Run all tests
./test-suite

# Run with verbose output
./test-suite verbose

# Run specific module
./test-suite storage      # Database tests (11 tests)
./test-suite config       # Configuration tests (14 tests)
./test-suite connection   # Connection tests (15 tests)
./test-suite imap         # IMAP tests (8 tests)
./test-suite smtp         # SMTP tests (7 tests)
./test-suite ui           # UI tests (18 tests)
./test-suite cli          # CLI tests (8 tests)
./test-suite composer     # Composer tests (12 tests)

# Get statistics
./test-suite count

# Show help
./test-suite help
```

### Using Python Runner

```bash
# Run all tests
python tests/run_tests.py

# Run specific module
python tests/run_tests.py storage
python tests/run_tests.py config
python tests/run_tests.py connection
python tests/run_tests.py imap
python tests/run_tests.py smtp
python tests/run_tests.py ui
python tests/run_tests.py cli
python tests/run_tests.py composer

# Verbose output
python tests/run_tests.py -v

# With coverage report
python tests/run_tests.py --cov

# Direct pytest commands
pytest tests/
pytest tests/test_storage.py
pytest tests/test_config.py::TestConfigurationDefaults
pytest tests/test_imap_client.py::TestEmailHeaderDecoding::test_decode_utf8_header -v
```

## 🔧 Working with Fixtures

### Available Fixtures (from conftest.py)

```python
# Temporary database for tests
def test_something(temp_db):
    # temp_db is a path to a temporary SQLite database
    pass

# Mock configuration
def test_something(mock_config):
    # mock_config is a dict with test IMAP/SMTP settings
    pass

# Sample email data
def test_something(test_email):
    # test_email is a single email dict
    pass

# Multiple sample emails
def test_something(test_emails):
    # test_emails is a list of email dicts
    pass

# Pre-configured IMAP mock
def test_something(mock_imap_connection):
    # mock_imap_connection is a MagicMock IMAP client
    pass

# Pre-configured SMTP mock
def test_something(mock_smtp_connection):
    # mock_smtp_connection is a MagicMock SMTP client
    pass

# Automatic env var cleanup (runs before/after each test)
# No need to use this directly - it's autouse
```

## 🛠️ Using Test Helpers

### DatabaseTestHelper

```python
from test_helpers import DatabaseTestHelper

# Create a single mock email
email = DatabaseTestHelper.create_mock_email(
    uid='test123',
    subject='Test Subject',
    sender='test@example.com',
    flagged=True
)

# Create multiple mock emails
emails = DatabaseTestHelper.create_mock_emails(
    count=5,
    sender='bulk@example.com'
)
```

### ConfigTestHelper

```python
from test_helpers import ConfigTestHelper

# Create test configuration
config = ConfigTestHelper.create_test_config(
    imap_host='imap.example.com',
    imap_port=993,
    smtp_host='smtp.example.com'
)
```

### IMAPTestHelper

```python
from test_helpers import IMAPTestHelper

# Create pre-configured IMAP mock
mock_imap = IMAPTestHelper.create_mock_imap()
```

### SMTPTestHelper

```python
from test_helpers import SMTPTestHelper

# Create pre-configured SMTP mock
mock_smtp = SMTPTestHelper.create_mock_smtp()
```

### ConsoleTestHelper

```python
from test_helpers import ConsoleTestHelper

# Capture console output
with ConsoleTestHelper.capture_console_output() as output:
    print("Hello")
assert "Hello" in output.getvalue()
```

### MockBuilder

```python
from test_helpers import MockBuilder

# Fluent builder for complex mocks
mock = (MockBuilder()
    .with_method('fetch', return_value=[])
    .with_method('select', return_value=('OK', []))
    .build())
```

## 📝 Writing New Tests

### Test Class Template

```python
"""Module docstring"""
import pytest
from unittest.mock import patch

from src.some_module import function_under_test
from .test_helpers import SomeTestHelper


class TestSomeFunctionality:
    """Descriptive class docstring"""

    def test_basic_scenario(self, temp_db, mock_config):
        """Test description"""
        # Setup
        test_data = SomeTestHelper.create_test_data()

        # Execute
        with patch('src.some_module.external_dependency'):
            result = function_under_test(test_data)

        # Assert
        assert result is not None

    def test_error_scenario(self, temp_db):
        """Test error handling"""
        with pytest.raises(ValueError):
            function_under_test(invalid_data)
```

### Best Practices

1. Group related tests in classes
2. Use fixtures from conftest.py
3. Leverage test_helpers.py for common operations
4. Clear test method names describing what's tested
5. One assertion focus per test (can have multiple related asserts)
6. Use mocking to isolate units under test
7. Test both success and failure paths

## 📊 Test Coverage

| Module         | Tests  | Focus                                |
| -------------- | ------ | ------------------------------------ |
| storage.py     | 11     | Database CRUD, search, backup        |
| config.py      | 14     | Configuration loading, validation    |
| connection.py  | 15     | IMAP/SMTP connection setup           |
| imap_client.py | 8      | Email fetching, parsing, attachments |
| smtp_client.py | 7      | Email sending, recipients, headers   |
| ui.py          | 18     | Display components, formatting       |
| cli.py         | 8      | Command dispatching                  |
| composer.py    | 12     | Email composition workflow           |
| **TOTAL**      | **93** | **All major functionality**          |

## 🔍 Debugging Tests

### Verbose Output

```bash
python tests/run_tests.py -v
# Shows each test as it runs

python tests/run_tests.py -vv
# Even more verbose with print statements visible
```

### Stop on First Failure

```bash
pytest tests/ -x
# Stops running tests after first failure
```

### Run Only Failed Tests

```bash
pytest tests/ --lf
# Re-runs last failed test(s)
```

### Run Tests Matching Pattern

```bash
pytest tests/test_storage.py -k "test_mark"
# Runs only tests with "mark" in the name
```

### Show Print Output

```bash
pytest tests/ -s
# Captures and displays print statements
```

### Debug with Pdb

```python
def test_something():
    import pdb; pdb.set_trace()  # Execution stops here
    result = function_under_test()
    assert result
```

## �� Common Issues & Solutions

### Issue: "Module not found" errors

**Solution**: Run tests from project root with `python tests/run_tests.py`

### Issue: Database locked errors

**Solution**: This is prevented by temp_db fixture - ensure tests using DB use temp_db

### Issue: Environment variable contamination

**Solution**: clear_env_vars autouse fixture handles this automatically

### Issue: Mock not being called

**Solution**: Ensure correct patch path matches import in file under test

### Issue: Test passes locally but fails in CI

**Solution**: Check for environment dependencies, use mocks for external services

## 📚 Key Concepts

### Fixtures

Reusable test setup/teardown - provide data and configuration to tests via function parameters.

### Mocking

Replace external dependencies (databases, APIs, file I/O) with controlled test doubles.

### Patches

Temporarily replace objects/functions for testing specific code paths.

### Class-Based Organization

Group related tests together for better maintainability and shared setup.

### Autouse Fixtures

Fixtures that run automatically before/after each test without being explicitly requested.

## 📖 Further Reading

- `README.md` - Comprehensive test documentation
- `TESTING_SUMMARY.md` - Complete refactoring summary
- `conftest.py` - Fixture definitions and configuration
- `test_helpers.py` - Helper class implementations
- Individual `test_*.py` files - Example implementations

## ✅ Checklist for New Tests

- [ ] Test is in appropriate test\_\*.py file
- [ ] Test class groups related tests together
- [ ] Test method name clearly describes what's tested
- [ ] Uses fixtures from conftest.py where applicable
- [ ] Uses helpers from test_helpers.py for common operations
- [ ] Includes docstring explaining test purpose
- [ ] Mocks external dependencies
- [ ] Tests both success and failure scenarios
- [ ] No hardcoded paths or environment dependencies
- [ ] Cleanup happens automatically (via fixtures)

---

**Last Updated**: After test suite refactoring
**Status**: ✅ Complete and verified
