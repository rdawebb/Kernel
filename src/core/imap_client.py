"""IMAP client for connecting to email server, fetching emails, and handling attachments"""

## TODO: refactor to remove any redundant functions, move parsing to separate module

import imaplib
import email
import datetime
import time
from email.header import decode_header
from email.utils import parsedate_tz
from contextlib import contextmanager
from utils.config import load_config
from core import storage_api
from utils import logger

config = load_config()

@contextmanager
def imap_connection(config):
    """Context manager for IMAP connections with automatic cleanup"""
    mail = connect_to_imap(config)
    if not mail:
        logger.error("Failed to connect to IMAP server")
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

def decode_email_header(header_value):
    """Decode email header handling encoding properly"""
    if not header_value:
        return ""
    
    try:
        decoded, encoding = decode_header(header_value)[0]
        if isinstance(decoded, bytes) and encoding:
            return decoded.decode(encoding)
        return str(decoded)
    except Exception:
        return str(header_value)

def decode_filename(filename):
    """Decode attachment filename handling encoding properly"""
    if not filename:
        return ""
    
    try:
        decoded_filename = decode_header(filename)[0]
        if isinstance(decoded_filename[0], bytes):
            return decoded_filename[0].decode(decoded_filename[1] or 'utf-8')
        else:
            return decoded_filename[0]
    except Exception:
        return str(filename)

def process_email_message(msg_part):
    """Process a message part and return email message object"""
    if isinstance(msg_part, tuple):
        return email.message_from_bytes(msg_part[1])
    return None

def connect_to_imap(config):
    try:
        port = config.get('imap_port', 993)
        if config.get('imap_use_ssl', True):
            mail = imaplib.IMAP4_SSL(config['imap_server'], port)
        else:
            mail = imaplib.IMAP4(config['imap_server'], port)
        
        mail.login(config['email'], config['password'])
        mail.select("inbox")

    except Exception as e:
        logger.error(f"Error connecting to IMAP server: {e}")
        print("Unable to connect to your email server. Please check your settings and try again.")
        return None
    
    return mail

## TODO: not necessary?
def fetch_inbox(config, limit=10):
    mail = connect_to_imap(config)
    if not mail:
        return []
    
    try:
        status, messages = mail.search(None, "ALL")
        
        if status != "OK":
            logger.error(f"Error connecting to inbox: {status}")
            print("Unable to connect to your email server. Please check your settings and try again.")
            return []
        
        email_ids = messages[0].split()
        latest_email_ids = email_ids[-limit:]
        emails = []

        for email_id in reversed(latest_email_ids):
            status, email_data = mail.fetch(email_id, "(RFC822)")
            
            if status != "OK":
                logger.error(f"Error fetching email ID {email_id}: {status}")
                print("Unable to fetch emails. Please check your connection and try again.")
                continue

            for msg_part in email_data:
                email_message = process_email_message(msg_part)
                if email_message:
                    emails.append(parse_email(email_message, email_id.decode()))

        return emails
    
    except Exception as e:
        logger.error(f"Error fetching emails: {e}")
        print("Sorry, something went wrong. Please check your settings or try again.")
        return []
    finally:
        try:
            mail.logout()
        except Exception:
            pass

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
            logger.error(f"Error searching for emails: {status}")
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
                    logger.error(f"Error fetching email ID {email_id}: {status}")
                    print("Unable to fetch emails. Please check your connection and try again.")
                    continue

                for msg_part in email_data:
                    email_message = process_email_message(msg_part)
                    if email_message:
                        email_dict = parse_email(email_message, email_id.decode())

                        storage_api.save_email_metadata(email_dict)
                        if email_dict.get("body"):
                            storage_api.save_email_body(email_dict.get("uid"), email_dict.get("body"))

                        emails_saved += 1
            except Exception as e:
                logger.error(f"Error processing email {email_id}: {e}")
                print("Sorry, something went wrong. Please check your settings or try again.")
                continue

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
    
def parse_email_date(date_str):
    """Parse RFC 2822 email date format and convert to local system timezone"""
    if not date_str:
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
    
    try:
        parsed_date = parsedate_tz(date_str)
        if parsed_date:
            timestamp = time.mktime(parsed_date[:9])
            
            if parsed_date[9] is not None:
                timestamp -= parsed_date[9]
            
            local_datetime = datetime.datetime.fromtimestamp(timestamp)
            return local_datetime.strftime("%Y-%m-%d"), local_datetime.strftime("%H:%M:%S")
    except Exception:
        pass
    
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

def parse_email(email_data, email_id):
    """Parse email data and return structured dictionary"""
    subject = ""
    sender = ""
    recipient = ""
    date_ = ""
    time_ = ""
    body = ""

    try:
        subject = decode_email_header(email_data.get("Subject"))
        sender = decode_email_header(email_data.get("From"))
        recipient = decode_email_header(email_data.get("To"))

        date_header = email_data.get("Date")
        date_, time_ = parse_email_date(date_header)

        attachment_list = _extract_attachment_filenames(email_data)
        attachments = ','.join(attachment_list)
        
        for part in email_data.walk() if email_data.is_multipart() else [email_data]:
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    body = part.get_payload(decode=True).decode()
                except UnicodeDecodeError:
                    body = part.get_payload(decode=True).decode('utf-8', errors='replace')
                except Exception:
                    body = str(part.get_payload())
                break

        return {
            "id": email_id,
            "uid": email_id,
            "from": sender,
            "to": recipient,
            "subject": subject,
            "date": date_,
            "time": time_,
            "body": body,
            "flagged": False,
            "attachments": attachments
        }

    except Exception as e:
        logger.error(f"Error parsing email: {e}")
        print("Sorry, something went wrong while parsing an email.")
        return {
            "id": email_id,
            "uid": email_id,
            "from": sender,
            "to": recipient,
            "subject": subject,
            "date": date_,
            "time": time_,
            "body": body,
            "flagged": False,
            "attachments": []
        }

def _fetch_email_by_uid(mail, email_uid):
    """Helper function to fetch and parse an email by UID"""

    status, messages = mail.search(None, f"UID {email_uid}")
    if status != "OK" or not messages[0]:
        logger.error(f"Email with UID {email_uid} not found")
        print("Sorry, unable to find this email. Please check your settings or try again.")
        return None

    status, email_data = mail.fetch(email_uid, "(RFC822)")
    if status != "OK":
        logger.error(f"Failed to fetch email {email_uid}")
        print("Sorry, failed to fetch email. Please check your settings or try again.")
        return None
    
    return email.message_from_bytes(email_data[0][1])

def _extract_attachment_filenames(email_message):
    """Helper function to extract just attachment filenames from an email message"""
    filenames = []
    
    for part in email_message.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        
        if "attachment" in content_disposition.lower():
            filename = part.get_filename()
            if filename:
                decoded_filename = decode_filename(filename)
                filenames.append(decoded_filename)
    
    return filenames

def _extract_attachments_from_email(email_message):
    """Helper function to extract attachment information from an email message"""
    attachments = []
    
    for part in email_message.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        
        if "attachment" in content_disposition.lower():
            filename = part.get_filename()
            if filename:
                decoded_filename = decode_filename(filename)
                
                content = part.get_payload(decode=True)
                if content:
                    attachments.append({
                        'filename': decoded_filename,
                        'content': content
                    })
    
    return attachments

def _save_attachment_to_disk(filename, content, download_path):
    """Helper function to save attachment content to disk with duplicate handling"""
    import os
    
    os.makedirs(download_path, exist_ok=True)
    
    file_path = os.path.join(download_path, filename)
    
    counter = 1
    original_file_path = file_path
    while os.path.exists(file_path):
        name, ext = os.path.splitext(original_file_path)
        file_path = f"{name}_{counter}{ext}"
        counter += 1
    
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return file_path

## TODO: not necessary? - combine with below
def download_all_attachments(config, email_uid, download_path="./attachments"):
    """Download all attachments from an email by UID"""
    with imap_connection(config) as mail:
        email_message = _fetch_email_by_uid(mail, email_uid)
        attachments = _extract_attachments_from_email(email_message)
        
        downloaded_files = []
        for attachment in attachments:
            file_path = _save_attachment_to_disk(
                attachment['filename'], 
                attachment['content'], 
                download_path
            )
            downloaded_files.append(file_path)
        
        return downloaded_files

def download_attachment_by_index(config, email_uid, attachment_index, download_path="./attachments"):
    """Download a specific attachment from an email by UID and index"""
    with imap_connection(config) as mail:
        email_message = _fetch_email_by_uid(mail, email_uid)
        attachments = _extract_attachments_from_email(email_message)

        if not attachments:
            logger.error(f"No attachments found for email {email_uid}")
            print("No attachments found. Please check and try again.")
            return None

        ## TODO: not necessary with TUI?
        if attachment_index >= len(attachments) or attachment_index < 0:
            logger.error(f"Invalid attachment index {attachment_index}. Available attachments: 0-{len(attachments)-1}")
            print("Invalid attachment index. Please check and try again.")
            return None

        attachment = attachments[attachment_index]
        file_path = _save_attachment_to_disk(
            attachment['filename'], 
            attachment['content'], 
            download_path
        )
        return file_path

## TODO: not necessary, but use function name
def get_attachment_list(config, email_uid):
    """Get list of attachment filenames from an email by UID without downloading"""
    with imap_connection(config) as mail:
        email_message = _fetch_email_by_uid(mail, email_uid)
        return _extract_attachment_filenames(email_message)

def delete_email(config, email_uid):
    """Delete an email by UID from the server"""
    with imap_connection(config) as mail:
        mail.uid('STORE', email_uid, '+FLAGS', r'(\Deleted)')
        mail.expunge()