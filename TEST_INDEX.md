# Kernel Test Suite Index

## 📚 Complete Documentation Index

1. **[tests/README.md](tests/README.md)** - Comprehensive overview of the test suite

   - Quick start guide (test-suite script & Python runner)
   - Architecture overview
   - Running tests
   - Using fixtures and helpers
   - Test patterns and best practices
   - Coverage map

2. **[tests/QUICK_REFERENCE.md](tests/QUICK_REFERENCE.md)** - Developer cheatsheet

   - File structure
   - Running tests (test-suite script & Python runner)
   - Fixture usage
   - Common issues & solutions
   - Debugging tips

3. **[TEST_INDEX.md](TEST_INDEX.md)** - This file (navigation)

---

## 🏗️ Architecture

### Core Files

```md
tests/
├── conftest.py              # Pytest fixtures (shared across all tests)
├── test_helpers.py          # Reusable helper classes (eliminates duplication)
├── run_tests.py             # Test runner script (flexible CLI)
└── *.py                     # Individual test modules
```

### Fixture System (conftest.py)

```python
@pytest.fixture
def temp_db():               # Temporary SQLite database per test

@pytest.fixture
def mock_config():           # Test configuration

@pytest.fixture
def test_email():            # Single email fixture

@pytest.fixture
def test_emails():           # List of emails fixture

@pytest.fixture
def mock_imap_connection():  # Pre-configured IMAP mock

@pytest.fixture
def mock_smtp_connection():  # Pre-configured SMTP mock

@pytest.fixture(autouse=True)
def clear_env_vars():        # Auto-cleanup of env vars
```

### Helper Classes (test_helpers.py)

```python
DatabaseTestHelper          # Email mock creation
IMAPTestHelper              # IMAP mock configuration
SMTPTestHelper              # SMTP mock configuration
ConfigTestHelper            # Configuration creation
ConsoleTestHelper           # Output capture
MockBuilder                 # Fluent mock builder
```

---

## � Test-Suite Script Guide

The `test-suite` bash script provides a user-friendly way to run tests with colored output and helpful feedback.

### Quick Start

```bash
# Make executable (first time only)
chmod +x test-suite

# Run all tests
./test-suite

# View help
./test-suite help
```

### All Commands

```bash
./test-suite                # Run all 93 tests (default)
./test-suite verbose        # Show detailed output with test names
./test-suite storage        # Run storage tests (11 tests)
./test-suite config         # Run config tests (14 tests)
./test-suite connection     # Run connection tests (15 tests)
./test-suite imap           # Run IMAP tests (8 tests)
./test-suite smtp           # Run SMTP tests (7 tests)
./test-suite ui             # Run UI tests (18 tests)
./test-suite composer       # Run composer tests (12 tests)
./test-suite cli            # Run CLI tests (8 tests)
./test-suite unit           # Run unit tests only (no integration)
./test-suite count          # Show test statistics by file
./test-suite help           # Show all options
```

### Features

- **Colored Output**: Easy to read with color-coded messages
- **Virtual Environment Support**: Automatically activates `.venv` if present
- **Error Handling**: Exits on failure for CI/CD compatibility
- **Test Breakdown**: Shows individual test counts per module

### Short Options

```bash
./test-suite -v             # Alias for verbose
./test-suite -h             # Alias for help
./test-suite --help         # Alias for help
```

---

## �📁 Test Module Reference

### Database Tests

**File**: `tests/test_storage.py` (180 lines, 11 tests)

Classes:

- `TestDatabaseManagement` - DB init & connection
- `TestEmailCRUDOperations` - Save, get, delete
- `TestEmailSearch` - Search functionality
- `TestEmailFlagging` - Mark flagged/unflagged
- `TestEmailMovement` - Move between tables
- `TestPendingEmailStatus` - Pending count
- `TestDatabaseBackupExport` - Backup/export
- `TestGetHighestUID` - UID tracking

### Configuration Tests

**File**: `tests/test_config.py` (195 lines, 14 tests)

Classes:

- `TestConfigManagerInitialization` - Creation & retrieval
- `TestConfigurationDefaults` - Default values
- `TestConfigurationValidation` - Validation
- `TestEnvironmentVariableHandling` - Env vars
- `TestDatabasePathConfiguration` - DB path
- `TestSSLConfiguration` - SSL/TLS settings

### Connection Tests

**File**: `tests/test_connection.py` (251 lines, 15 tests)

Classes:

- `TestIMAPConnection` - IMAP setup
- `TestIMAPContextManager` - IMAP context manager
- `TestSMTPConnectionSSL` - SMTP SSL
- `TestSMTPConnectionStartTLS` - SMTP STARTTLS
- `TestSMTPConnectionErrors` - Error handling
- `TestConnectionConfiguration` - Config-based setup

### IMAP Operation Tests

**File**: `tests/test_imap_client.py` (185 lines, 8 tests)

Classes:

- `TestIMAPConnection` - Connection handling
- `TestFetchNewEmails` - New email detection
- `TestDeleteEmail` - Email deletion

### SMTP Operation Tests

**File**: `tests/test_smtp_client.py` (151 lines, 7 tests)

Classes:

- `TestSendEmail` - Email sending, recipients, headers, errors

### UI Component Tests

**File**: `tests/test_ui.py` (280 lines, 18 tests)

Classes:

- `TestInboxDisplay` - Inbox rendering
- `TestEmailDisplay` - Email viewing
- `TestSearchResultsDisplay` - Search display
- `TestUIDataFormatting` - Data formatting
- `TestUIErrorHandling` - Error handling

### CLI Command Tests

**File**: `tests/test_cli.py` (109 lines, 8 tests)

Classes:

- `TestCommandDispatching` - Command routing
- `TestSearchCommand` - Search command
- `TestViewCommand` - View command
- `TestDeleteCommand` - Delete command
- `TestFlagCommand` - Flag command

### Email Composer Tests

**File**: `tests/test_composer.py` (231 lines, 12 tests)

Classes:

- `TestComposeEmailWorkflow` - Composition flow
- `TestComposeEmailValidation` - Input validation
- `TestComposeSendActions` - Send/draft/schedule
- `TestComposeMultilineBody` - Multiline text handling
- `TestComposeErrorHandling` - Error scenarios

### Infrastructure Tests

**File**: `tests/test_helpers.py` (167 lines)

Helper classes for test infrastructure and mock creation.

---

## 🚀 Running Tests

### All Tests

```bash
python tests/run_tests.py
```

### By Module

```bash
python tests/run_tests.py storage       # Database tests
python tests/run_tests.py config        # Configuration tests
python tests/run_tests.py connection    # Connection tests
python tests/run_tests.py imap          # IMAP tests
python tests/run_tests.py smtp          # SMTP tests
python tests/run_tests.py ui            # UI tests
python tests/run_tests.py cli           # CLI tests
python tests/run_tests.py composer      # Composer tests
```

### With Options

```bash
python tests/run_tests.py -v            # Verbose
python tests/run_tests.py --cov         # Coverage report
```

### Direct pytest

```bash
pytest tests/                           # All tests
pytest tests/test_storage.py            # Specific module
pytest tests/test_storage.py -v         # Verbose
pytest tests/test_storage.py::TestDatabaseManagement  # Specific class
pytest tests/test_storage.py::TestDatabaseManagement::test_initialize_db_creates_tables  # Specific test
```

---

## 📊 Test Statistics

| Category             | Count  |
| -------------------- | ------ |
| Test Modules         | 8      |
| Test Classes         | 40+    |
| Test Methods         | 93     |
| Lines of Test Code   | 1,800+ |
| Infrastructure Lines | 259    |
| Total Lines          | 2,059  |

---

## 🎯 Coverage Map

```md
src/core/
├── storage_api.py          ✅ test_storage.py (11 tests)
├── db_manager.py           ✅ test_storage.py (11 tests)
├── email_operations.py     ✅ test_storage.py (11 tests)
├── email_search.py         ✅ test_storage.py (11 tests)
├── imap_client.py          ✅ test_imap_client.py (8 tests)
├── smtp_client.py          ✅ test_smtp_client.py (7 tests)
└── summariser.py           ❌ Not integrated yet

src/cli/
└── cli.py                  ✅ test_cli.py (8 tests)

src/ui/
├── composer.py             ✅ test_composer.py (12 tests)
├── inbox_viewer.py         ✅ test_ui.py (18 tests)
├── email_viewer.py         ✅ test_ui.py (18 tests)
└── search_viewer.py        ✅ test_ui.py (18 tests)

src/utils/
├── config_manager.py       ✅ test_config.py (14 tests)
└── scheduler.py            ✅ (legacy test_send_later.py)

Connections:
├── IMAP                    ✅ test_connection.py (15 tests)
├── SMTP SSL                ✅ test_connection.py (15 tests)
└── SMTP STARTTLS          ✅ test_connection.py (15 tests)

Total: 93 tests ✅
```

---

## 🛠️ Key Patterns

### Writing a New Test

```python
def test_something_specific(self, temp_db, mock_config):
    """Clear description of what's being tested"""
    # Setup
    test_data = DatabaseTestHelper.create_mock_email()

    # Execute
    with patch('module.dependency'):
        result = function_under_test(test_data)

    # Assert
    assert result is not None
```

### Using Fixtures

```python
def test_with_fixtures(self, temp_db, mock_config, test_email):
    # temp_db:       Temporary database path
    # mock_config:   Test configuration dict
    # test_email:    Sample email data
    pass
```

### Using Helpers

```python
from test_helpers import DatabaseTestHelper

email = DatabaseTestHelper.create_mock_email(
    uid='test123',
    subject='Test',
    flagged=True
)
```

---

## 🔍 Debugging

### Verbose Output

```bash
python tests/run_tests.py -v
```

### Stop on First Failure

```bash
pytest tests/ -x
```

### Show Print Statements

```bash
pytest tests/ -s
```

### Run Specific Test

```bash
pytest tests/test_storage.py::TestDatabaseManagement::test_initialize_db_creates_tables
```

### Debug with pdb

```python
def test_something():
    import pdb; pdb.set_trace()
    result = function_under_test()
```

---

## 📋 Maintenance

### Adding New Tests

1. Choose appropriate test module
2. Follow existing class/method patterns
3. Use fixtures and helpers
4. Add clear docstrings
5. Test success AND failure scenarios

### Updating Tests

1. Edit test in appropriate file
2. Run with `python tests/run_tests.py -v`
3. Verify related tests still pass
4. Update documentation if needed

### Extending Helpers

1. Add method to appropriate helper class
2. Follow DRY principle
3. Add docstring
4. Test via multiple test methods

---

## 📚 Further Resources

- **[tests/README.md](tests/README.md)** - Full documentation
- **[tests/QUICK_REFERENCE.md](tests/QUICK_REFERENCE.md)** - Quick guide
- **[TESTING_SUMMARY.md](TESTING_SUMMARY.md)** - Detailed summary
- **[pytest documentation](https://docs.pytest.org/)**
- **[unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)**

---

## ✅ Checklist for Contributors

Before submitting new tests:

- [ ] Tests are in appropriate module
- [ ] Tests use fixtures from conftest.py
- [ ] Tests use helpers from test_helpers.py
- [ ] Methods have clear names
- [ ] Docstrings explain what's tested
- [ ] External dependencies are mocked
- [ ] Both success and error paths tested
- [ ] Tests run with `python tests/run_tests.py`
- [ ] No hardcoded paths/env vars
- [ ] Related existing tests still pass

---

## 📞 Getting Help

### Common Issues

**Module not found**
→ Run from project root: `python tests/run_tests.py`

**Database locked**
→ Use `temp_db` fixture (automatic isolation)

**Mock not called**
→ Check patch path matches import

**Environment variables issue**
→ `clear_env_vars` handles cleanup automatically

### More Help

See **[tests/QUICK_REFERENCE.md](tests/QUICK_REFERENCE.md)** for troubleshooting section.

---

**Last Updated**: After comprehensive test suite refactoring
**Status**: ✅ Complete and Verified
**Framework**: pytest
**Coverage**: ~115 tests across 8 modules
