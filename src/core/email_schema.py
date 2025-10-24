"""Email table schema definitions and column management"""

## TODO: consolidate schema definitions and remove redundancy

class EmailSchemaManager:
    """Manages email table schemas and column definitions"""
    
    # Base columns for all email tables
    _BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS = """uid, subject, sender as "from", recipient as "to", date, time, attachments"""
    
    # Additional column definitions
    _FLAGGED_COLUMN = "flagged"
    _BODY_COLUMN = "body"
    _DELETED_DATE_COLUMN = "deleted_at"
    _SENT_STATUS = "sent_status"
    _SEND_AT = "send_at"
    
    # Standard column combinations
    STANDARD_EMAIL_COLUMNS = f"{_BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS}, {_FLAGGED_COLUMN}"
    STANDARD_EMAIL_COLUMNS_WITH_BODY = f"{_BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS}, {_FLAGGED_COLUMN}, {_BODY_COLUMN}"
    STANDARD_EMAIL_COLUMNS_NO_FLAG = _BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS
    STANDARD_EMAIL_COLUMNS_NO_FLAG_WITH_BODY = f"{_BASE_EMAIL_COLUMNS_WITH_ATTACHMENTS}, {_BODY_COLUMN}"
    
    # Standard ordering
    STANDARD_EMAIL_ORDER = "ORDER BY date DESC, time DESC"
    
    # Schema definitions
    _BASE_SCHEMA_COLUMNS = """uid TEXT PRIMARY KEY,
        subject TEXT,
        sender TEXT,
        recipient TEXT,
        date TEXT,
        time TEXT,
        body TEXT,
        attachments TEXT DEFAULT ''"""

    FLAGGED_COLUMN_DEF = "flagged BOOLEAN DEFAULT 0"
    DELETED_AT_COLUMN_DEF = "deleted_at TEXT"
    SENT_STATUS_COLUMN_DEF = "sent_status TEXT DEFAULT 'pending'"
    SEND_AT_COLUMN_DEF = "send_at TEXT"
    
    def get_columns_for_table(self, table_name: str, include_body: bool = False) -> str:
        """Get appropriate columns for a specific table"""
        if table_name == "inbox":
            return self.STANDARD_EMAIL_COLUMNS_WITH_BODY if include_body else self.STANDARD_EMAIL_COLUMNS
        elif table_name == "sent_emails":
            base = self.STANDARD_EMAIL_COLUMNS_NO_FLAG_WITH_BODY if include_body else self.STANDARD_EMAIL_COLUMNS_NO_FLAG
            return f"{base}, {self._SENT_STATUS}, {self._SEND_AT}"
        elif table_name == "deleted_emails":
            base = self.STANDARD_EMAIL_COLUMNS_NO_FLAG_WITH_BODY if include_body else self.STANDARD_EMAIL_COLUMNS_NO_FLAG
            return f"{base}, {self._DELETED_DATE_COLUMN}"
        else:  # drafts or other tables
            return self.STANDARD_EMAIL_COLUMNS_NO_FLAG_WITH_BODY if include_body else self.STANDARD_EMAIL_COLUMNS_NO_FLAG
    
    def get_insert_columns_for_table(self, table_name: str) -> str:
        """Get actual column names (without aliases) for INSERT statements"""

        base_columns = "uid, subject, sender, recipient, date, time, body, attachments"

        if table_name == "inbox":
            return f"{base_columns}, flagged"
        elif table_name == "sent_emails":
            return f"{base_columns}, sent_status, send_at"
        elif table_name == "deleted_emails":
            return f"{base_columns}, deleted_at"
        else:  # drafts
            return base_columns
    
    def create_email_table_sql(self, table_name: str, include_flagged: bool = False, 
                              include_deleted: bool = False, include_sent_status: bool = False, 
                              include_send_at: bool = False) -> str:
        """Create SQL for standardized email table with optional columns"""
        schema = self._BASE_SCHEMA_COLUMNS
        
        if include_flagged:
            schema = schema.replace("body TEXT,", f"{self.FLAGGED_COLUMN_DEF},\n    body TEXT,")
        
        additional_columns = []
        
        if include_deleted:
            additional_columns.append(self.DELETED_AT_COLUMN_DEF)
        
        if include_sent_status:
            additional_columns.append(self.SENT_STATUS_COLUMN_DEF)
        
        if include_send_at:
            additional_columns.append(self.SEND_AT_COLUMN_DEF)
        
        if additional_columns:
            additional_cols_str = ",\n    " + ",\n    ".join(additional_columns)
            schema = schema.replace("attachments TEXT DEFAULT ''", f"attachments TEXT DEFAULT ''{additional_cols_str}")

        return f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                {schema}
            )
        """
    
    def get_table_config(self, table_name: str) -> dict:
        """Get configuration for table creation"""
        configs = {
            "inbox": {"include_flagged": True},
            "sent_emails": {"include_sent_status": True, "include_send_at": True},
            "drafts": {},
            "deleted_emails": {"include_deleted": True}
        }
        return configs.get(table_name, {})
