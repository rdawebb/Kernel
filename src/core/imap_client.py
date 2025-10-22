"""IMAP client for connecting to email server and fetching emails"""

import imaplib
from contextlib import contextmanager
from ..utils.config_manager import ConfigManager
from . import storage_api
from ..utils.log_manager import get_logger, log_call
from ..utils.email_parser import parse_email, process_email_message

logger = get_logger(__name__)
config_manager = ConfigManager()

@contextmanager
def imap_connection(account_config):
    """Context manager for IMAP connections with automatic cleanup"""
    mail = connect_to_imap(account_config)
    if not mail:
        logger.error("Failed to establish IMAP connection")
        print("Unable to connect to your email server. Please check your settings and try again.")
        yield None
        return
    try:
        yield mail
    finally:
        try:
            mail.close()
            mail.logout()
        except Exception:
            pass

@log_call
def connect_to_imap(account_config):
    """Connect to IMAP server with SSL/TLS support"""
    try:
        imap_server = account_config.get('imap_server') or config_manager.get_config('account.imap_server')
        imap_port = account_config.get('imap_port') or config_manager.get_config('account.imap_port', 993)
        use_tls = account_config.get('use_tls', config_manager.get_config('account.use_tls', True))
        email = account_config.get('email') or config_manager.get_config('account.email')
        
        if use_tls:
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
        else:
            mail = imaplib.IMAP4(imap_server, imap_port)
        
        mail.login(email, account_config['password'])
        mail.select("inbox")
        logger.info(f"Connected to IMAP server {imap_server}:{imap_port}")

    except Exception as e:
        logger.error(f"Error connecting to IMAP server: {e}")
        print("Unable to connect to your email server. Please check your settings and try again.")
        return None
    
    return mail

@log_call
def fetch_new_emails(account_config, fetch_all=False):
    """Fetch new emails from IMAP server and save to database"""
    
    mail = connect_to_imap(account_config)
    if not mail:
        return 0
    
    try:
        if fetch_all:
            status, messages = mail.search(None, "ALL")
        else:
            highest_uid = storage_api.get_highest_uid()
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

        fetch_method = mail.uid if not fetch_all and storage_api.get_highest_uid() else mail

        for email_id in email_ids:
            try:
                status, email_data = fetch_method('fetch', email_id, "(RFC822)")
                
                if status != "OK":
                    logger.error(f"Error fetching email ID {email_id}: {status}")
                    print("Unable to fetch emails. Please check your connection and try again.")
                    continue

                for msg_part in email_data:
                    email_message = process_email_message(msg_part)
                    if email_message:
                        email_dict = parse_email(email_message, email_id.decode())

                        storage_api.save_email_metadata(email_dict)
                        # Note: body is already included in save_email_metadata

                        emails_saved += 1
            except Exception as e:
                logger.error(f"Error processing email {email_id}: {e}")
                print("Sorry, something went wrong. Please check your settings or try again.")
                continue

        logger.info(f"Fetched and saved {emails_saved} new emails from IMAP server")
        return emails_saved
    
    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
        print("Sorry, something went wrong. Please check your settings or try again.")
        return 0
    finally:
        try:
            mail.logout()
        except Exception:
            pass

@log_call
def delete_email(account_config, email_uid):
    """Delete an email by UID from the server"""
    with imap_connection(account_config) as mail:
        if mail:
            mail.uid('STORE', email_uid, '+FLAGS', r'(\Deleted)')
            mail.expunge()
            logger.info(f"Deleted email UID {email_uid} from IMAP server")
