# Email Module

Asynchronous email protocol handling for IMAP, SMTP, and email parsing.

## Architecture

```md
email/
├── __init__.py         # Public API exports
├── constants.py        # Shared constants (timeouts, batch sizes)
├── parser.py           # Email parsing with error recovery
├── imap/               # IMAP client
│   ├── __init__.py
│   ├── client.py       # High-level operations
│   └── connection.py   # Connection lifecycle
└── smtp/               # SMTP client
    ├── __init__.py
    ├── client.py       # High-level operations
    └── connection.py   # Connection lifecycle
```

## Design Principles

### 1. Separation of Concerns

- **Client classes**: High-level operations (fetch, send, delete, etc.)
- **Connection classes**: Low-level lifecyle (connect, reconnect, health checks, etc.)
- **Parser**: Message parsing with error recovery

### 2. Async First

All operations are asynchronous using 'asyncio' and async libraries:

- IMAP: 'aioimaplib'
- SMTP: 'aiosmtplib'
- Parsing: 'fast-mail-parser' (sync, but very fast)

### 3. Automatic Connection Management

- TTL-based expiration (configurable per protocol)
- Health checks via NOOP before operations
- Automatic reconnection on connection loss
- Connection statistics tracking

### 4. Error Recovery

- Transient errors (server busy, timeouts) -> automatic retry with exponential backoff
- Parse errors -> skip malformed emails, continue sync
- Auth failures -> prompt for new credentials, retry
- All errors logged with structured context

### 5. Observability

- Structured logging (JSON-friendly 'extra' fields)
- Connection statistics (operations, reconnections, timing)
- Operation timing (search, fetch, send)
- Performance metrics (emails/second, average send time)

## Usage

### IMAP Operations

```python
from src.core.email import get_imap_client, SyncMode

imap = get_imap_client(config)

# Fetch new emails
count = await imap.fetch_new_emails(SyncMode.INCREMENTAL)

# Email operations
await imap.delete_email('12345')
await imap.move_email('12345', 'Archive')
await imap.update_read_status('12345', read=True)
await imap.update_flag_status('12345', flagged=True)

# Folder operations
folders = await imap.get_folder_list()
status = await imap.get_folder_status("INBOX")

# Connection stats
stats = imap.get_connection_stats()
print(f"Operations: {stats['operations_count']}")
```

### SMTP Operations

```python
from src.core.email import get_smtp_client

smtp = get_smtp_client(config)

# Send email
await smtp.send_email(
    to_email="user@example.com",
    subject="Hello",
    body="Test message",
    cc=["user2@example.com"]
    bcc=["user3@example.com"]
)

# Connection stats
stats = smtp.get_connection_stats()
print(f"Emails sent: {stats['emails_sent']}")
```

### Email Parsing

```python
from src.core.email import EmailParser

# Lenient mode (returns None on failure)
email_dict = EmailParser.parse_from_bytes(raw_bytes, uid="12345")
if email_dict is None:
    print("Malformed email, skipping")

# Strict mode (raises ValidationError on failure)
email_dict = EmailParser.parse_from_bytes(
    raw_bytes, uid="12345", strict=True
)
```

## Configuration

### Timeouts

Customise in constants.py or in config:

```toml
imap_connection_ttl = 3600 # 1 hour (default)
smtp_connection_ttl = 1800 # 30 minutes (default)
```

### Batch Sizes

Tune performance in constants.py

```python
class BatchSizes:
    IMAP_FETCH_BATCH = 50   # Emails per fetch batch
    DB_SAVE_BATCH = 100     # Emails per database batch
    IMAP_FETCH_DELAY = 0.1  # Seconds between batches
```

## Error Handling

All operations raise exceptions from 'src.utils.errors':

- 'IMAPError': IMAP operation failed
- 'SMTPError': SMTP operation failed
- 'NetworkTimeoutError': Operation timed out
- 'AuthenticationError': Invalid credentials
- 'ValidationError': Parse/validation failed
- 'NetworkError': Network connectivity issue

Transient errors (421, 450, 451, 452, SMTP codes, connection drops) are
automatically retried. Non-transient errors raise immediately.

## Testing

### Unit Tests

```bash
./test imap         # Test IMAP
./test smtp         # Test SMTP
./test connections  # Test connections
./test email        # Test complete email module
```

### Integration Tests

Requires real IMAP/SMTP credentials

```bash
./test integration  # Test real connections
```

### Manual Testing

```bash
./kernel    # Run CLI script

# Test sync
sync

# Test compose
compose

# Check logs for structured data
logs sync
```

## Maintenance

### Adding New IMAP Operations

1. Add method to 'IMAPClient' in 'imap/client.py'
2. Use 'self.\_connection.\_ensure_connection()' for client
3. Use 'self.\_connection.\_check_response()' for validation
4. Use constants from 'constants.py' for timeouts
5. Add stuctured logging with operation context
6. Add to '**all**' exports in 'imap/**init**.py'

### Adding New SMTP Operations

1. Add method to 'SMTPClient' in 'smtp/client.py'
2. Use 'self.\_connection.\_ensure_connection()' for client
3. Implement retry logic for transient errors
4. Track in connection stats
5. Add stuctured logging with operation context
6. Add to '**all**' exports in 'imap/**init**.py'

### Modifying Parser

1. Update '\_to_dict()' for new fields
2. Add field extraction helper (e.g. '\_extract_new_field()')
3. Ensure lenient mode returns None on failure
4. Add unit tests for edge cases
5. Update doctsrings with new field info
