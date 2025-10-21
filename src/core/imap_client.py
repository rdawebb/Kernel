"""IMAP client for connecting to email server and fetching emails"""

import imaplib
from contextlib import contextmanager
from src.utils.config import load_config
from . import storage_api
from src.utils import log_manager
from src.utils.email_parser import parse_email, process_email_message

config = load_config()

@contextmanager
def imap_connection(config):
    """Context manager for IMAP connections with automatic cleanup"""
    mail = connect_to_imap(config)
    if not mail:
        log_manager.error("Failed to connect to IMAP server")
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

def connect_to_imap(config):
    """Connect to IMAP server with SSL/TLS support"""
    try:
        port = config.get('imap_port', 993)
        if config.get('imap_use_ssl', True):
            mail = imaplib.IMAP4_SSL(config['imap_server'], port)
        else:
            mail = imaplib.IMAP4(config['imap_server'], port)
        
        mail.login(config['email'], config['password'])
        mail.select("inbox")

    except Exception as e:
        log_manager.error(f"Error connecting to IMAP server: {e}")
        print("Unable to connect to your email server. Please check your settings and try again.")
        return None
    
    return mail

def fetch_new_emails(config, fetch_all=False):
    """Fetch new emails from IMAP server and save to database"""
    
    mail = connect_to_imap(config)
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
            log_manager.error(f"Error searching for emails: {status}")
            print("Unable to fetch emails. Please check your connection and try again.")
            return 0
        
        email_ids = messages[0].split()
        if not email_ids or email_ids == [b'']:
            return 0
        
        emails_saved = 0

        fetch_method = mail.uid if not fetch_all and storage_api.get_highest_uid() else mail

        for email_id in email_ids:
            try:
                status, email_data = fetch_method('fetch', email_id, "(RFC822)")
                
                if status != "OK":
                    log_manager.error(f"Error fetching email ID {email_id}: {status}")
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
                log_manager.error(f"Error processing email {email_id}: {e}")
                print("Sorry, something went wrong. Please check your settings or try again.")
                continue

        return emails_saved
    
    except Exception as e:
        log_manager.error(f"Error fetching emails: {e}")
        print("Sorry, something went wrong. Please check your settings or try again.")
        return 0
    finally:
        try:
            mail.logout()
        except Exception:
            pass

def delete_email(config, email_uid):
    """Delete an email by UID from the server"""
    with imap_connection(config) as mail:
        if mail:
            mail.uid('STORE', email_uid, '+FLAGS', r'(\Deleted)')
            mail.expunge()
