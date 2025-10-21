"""Email parsing utilities for processing email messages"""

import email
import datetime
from email.header import decode_header
from email.utils import parsedate_tz
from . import log_manager


def process_email_message(msg_part):
    """Convert message tuple to email message object."""
    if isinstance(msg_part, tuple):
        return email.message_from_bytes(msg_part[1])
    return None

def decode_email_header(header_value):
    """Decode email header with proper encoding handling."""
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
    """Decode attachment filename with proper encoding handling."""
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

def parse_email_date(date_str):
    """Parse RFC 2822 email date to local system timezone."""
    if not date_str:
        now = datetime.datetime.now()
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")
    
    try:
        parsed_date = parsedate_tz(date_str)
        if parsed_date[9] is not None:
            timestamp = email.utils.mktime_tz(parsed_date)
            local_datetime = datetime.datetime.fromtimestamp(timestamp)
            return local_datetime.strftime("%Y-%m-%d"), local_datetime.strftime("%H:%M:%S")

    except Exception:
        pass
    
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

def _extract_body(email_data):
    """Extract plain text body from email message."""
    for part in email_data.walk() if email_data.is_multipart() else [email_data]:
        content_type = part.get_content_type()
        content_disposition = str(part.get("Content-Disposition"))
        if content_type == "text/plain" and "attachment" not in content_disposition:
            try:
                return part.get_payload(decode=True).decode()
            except UnicodeDecodeError:
                return part.get_payload(decode=True).decode('utf-8', errors='replace')
            except Exception:
                return str(part.get_payload())
    return ""

def parse_email(email_data, email_uid):
    """Parse email data into structured dictionary."""
    from src.utils.attachment_utils import _extract_attachments
    
    try:
        subject = decode_email_header(email_data.get("Subject"))
        sender = decode_email_header(email_data.get("From"))
        recipient = decode_email_header(email_data.get("To"))
        date_header = email_data.get("Date")
        date_, time_ = parse_email_date(date_header)
        attachment_list = _extract_attachments(email_data, include_content=False)
        attachments = ','.join([att['filename'] for att in attachment_list])
        body = _extract_body(email_data)

        return {
            "uid": email_uid,
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
        log_manager.error(f"Error parsing email: {e}")
        print("Sorry, something went wrong while parsing an email.")
        return {
            "uid": email_uid,
            "from": "",
            "to": "",
            "subject": "",
            "date": "",
            "time": "",
            "body": "",
            "flagged": False,
            "attachments": ""
        }
