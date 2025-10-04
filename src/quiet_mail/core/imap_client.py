import imaplib
import email
import datetime
import time
from email.header import decode_header
from email.utils import parsedate_tz
from quiet_mail.utils.config import load_config

config = load_config()

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
        print(f"Error connecting to email server: {e}")
        return None
    
    return mail

def fetch_inbox(config, limit=10):
    mail = connect_to_imap(config)
    if not mail:
        return []
    
    try:
        status, messages = mail.search(None, "ALL")
        
        if status != "OK":
            print(f"Error connecting to inbox: {status}")
            return []
        
        email_ids = messages[0].split()
        latest_email_ids = email_ids[-limit:]
        emails = []

        for email_id in reversed(latest_email_ids):
            status, email_data = mail.fetch(email_id, "(RFC822)")
            
            if status != "OK":
                print(f"Error fetching email ID {email_id}: {status}")
                continue

            for msg_part in email_data:
                if isinstance(msg_part, tuple):
                    email_data = email.message_from_bytes(msg_part[1])
                    emails.append(parse_email(email_data, email_id.decode()))

        return emails
    
    except Exception as e:
        print(f"Error fetching emails: {e}")
        return []
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
            
            # Adjust for the email's timezone offset to get UTC
            if parsed_date[9] is not None:
                timestamp -= parsed_date[9]
            
            # Convert UTC timestamp to local system time
            local_datetime = datetime.datetime.fromtimestamp(timestamp)
            return local_datetime.strftime("%Y-%m-%d"), local_datetime.strftime("%H:%M:%S")
    except Exception:
        pass
    
    now = datetime.datetime.now()
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

def parse_email(email_data, email_id):
    subject = ""
    sender = ""
    recipient = ""
    date_ = ""
    time_ = ""
    body = ""

    try:
        subject_header = email_data.get("Subject")
        if subject_header:
            subject, encoding = decode_header(subject_header)[0]
            subject = subject.decode(encoding) if isinstance(subject, bytes) and encoding else str(subject)
        
        sender_header = email_data.get("From")
        if sender_header:
            sender, encoding = decode_header(sender_header)[0]
            sender = sender.decode(encoding) if isinstance(sender, bytes) and encoding else str(sender)

        recipient_header = email_data.get("To")
        if recipient_header:
            recipient, encoding = decode_header(recipient_header)[0]
            recipient = recipient.decode(encoding) if isinstance(recipient, bytes) and encoding else str(recipient)

        date_header = email_data.get("Date")
        date_, time_ = parse_email_date(date_header)

        body = ""
        for part in email_data.walk() if email_data.is_multipart() else [email_data]:
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            # Only process plain text parts that aren't attachments
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    body = part.get_payload(decode=True).decode()
                except UnicodeDecodeError:
                    # Handle encoding issues gracefully
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
            "body": body
        }

    except Exception as e:
        print(f"Error parsing email: {e}")
        return {
            "id": email_id,
            "uid": email_id,
            "from": sender,
            "to": recipient,
            "subject": subject,
            "date": date_,
            "time": time_,
            "body": body
        }