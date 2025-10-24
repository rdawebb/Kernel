"""IMAP client for email operations - fetch, delete, and synchronization."""

from enum import Enum
from typing import Optional
from . import storage_api
from .imap_connection import imap_connection, get_account_info
from .uid_cache import UIDCache
from ..utils.email_parser import parse_email, process_email_message
from ..utils.log_manager import get_logger, log_call

logger = get_logger(__name__)


class SyncMode(Enum):
    """Email sync modes."""
    INCREMENTAL = "incremental"  # Fetch only new emails since last sync
    FULL = "full"  # Fetch all emails from server


class IMAPClient:
    """Handles IMAP operations: fetch, delete, and email synchronization."""
    
    def __init__(self, account_config: Optional[dict] = None):
        """Initialize IMAP client with optional account config."""

        self.account_config = account_config or get_account_info()
        self.uid_cache = UIDCache()
    
    @log_call
    def _process_and_save_email(self, email_id: bytes, email_data: list) -> bool:
        """Process email data and save if new."""

        for msg_part in email_data:
            email_message = process_email_message(msg_part)
            if not email_message:
                continue
            email_dict = parse_email(email_message, email_id.decode())
            if not storage_api.email_exists("inbox", email_dict['uid']):
                storage_api.save_email_metadata(email_dict)
                return True
        return False
    
    @log_call
    def fetch_new_emails(self, sync_mode: SyncMode = SyncMode.INCREMENTAL) -> int:
        """Fetch emails from IMAP server and save to database."""

        if not self.account_config:
            logger.error("Account config not available")
            print("Account configuration not available. Please configure your email account.")
            return 0
        
        with imap_connection(self.account_config) as mail:
            
            if not mail:
                return 0
            
            try:
                # Search for emails
                if sync_mode == SyncMode.FULL:
                    status, messages = mail.search(None, "ALL")
                else:
                    highest_uid = self.uid_cache.get(db_fallback_func=storage_api.get_highest_uid)
                    if highest_uid:
                        status, messages = mail.uid('search', None, f'UID {highest_uid + 1}:*')
                    else:
                        status, messages = mail.search(None, "ALL")
                
                if status != "OK":
                    logger.error(f"Error searching for emails: {status}")
                    print("Unable to fetch emails. Please check your connection and try again.")
                    return 0
                
                email_ids = messages[0].split()
                if not email_ids or email_ids == [b'']:
                    logger.debug("No new emails found")
                    return 0
                
                emails_saved = 0
                use_uid = sync_mode == SyncMode.INCREMENTAL and self.uid_cache.get() is not None
                
                # Fetch and process emails
                for email_id in email_ids:
                    try:
                        status, email_data = (mail.uid('fetch', email_id, "(RFC822)") if use_uid
                                            else mail.fetch(email_id, "(RFC822)"))
                        
                        if status != "OK":
                            logger.error(f"Error fetching email ID {email_id}: {status}")
                            continue
                        
                        if self._process_and_save_email(email_id, email_data):
                            emails_saved += 1
                    except Exception as e:
                        logger.error(f"Error processing email {email_id}: {e}")
                        continue
                
                logger.info(f"Fetched and saved {emails_saved} new emails from IMAP server")
                
                # Update cache with new highest UID
                if emails_saved > 0:
                    new_highest_uid = storage_api.get_highest_uid()
                    if new_highest_uid is not None:
                        self.uid_cache.update(new_highest_uid)
                
                return emails_saved
            
            except Exception as e:
                logger.error(f"Error fetching emails: {e}")
                print("Sorry, something went wrong. Please check your settings or try again.")
                return 0
    
    @log_call
    def delete_email(self, email_uid: str) -> bool:
        """Delete an email by UID from the server."""
        if not self.account_config:
            logger.error("Account config not available")
            print("Account configuration not available. Please configure your email account.")
            return False
        
        with imap_connection(self.account_config) as mail:
            if not mail:
                return False
            
            try:
                mail.uid('STORE', email_uid, '+FLAGS', r'(\Deleted)')
                mail.expunge()
                logger.info(f"Deleted email UID {email_uid} from IMAP server")
                return True
            except Exception as e:
                logger.error(f"Error deleting email UID {email_uid}: {e}")
                print(f"Failed to delete email UID {email_uid}")
                return False
