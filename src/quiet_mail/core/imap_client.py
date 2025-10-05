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

def fetch_new_emails(config, fetch_all=False):
    """Fetch new emails from IMAP server and save to database"""
    from quiet_mail.core import storage
    
    mail = connect_to_imap(config)
    if not mail:
        return 0
    
    try:
        if fetch_all:
            status, messages = mail.search(None, "ALL")
        else:
            highest_uid = storage.get_highest_uid()
            if highest_uid:
                status, messages = mail.uid('search', None, f'UID {highest_uid + 1}:*')
            else:
                # No emails in database, fetch recent emails instead of all
                status, messages = mail.search(None, "ALL")
        
        if status != "OK":
            print(f"Error searching for emails: {status}")
            return 0
        
        email_ids = messages[0].split()
        if not email_ids or email_ids == [b'']:
            return 0
        
        emails_saved = 0
        
        # For UID search, use uid fetch; for regular search, use regular fetch
        fetch_method = mail.uid if not fetch_all and storage.get_highest_uid() else mail
        
        for email_id in email_ids:
            try:
                status, email_data = fetch_method('fetch', email_id, "(RFC822)")
                
                if status != "OK":
                    print(f"Error fetching email ID {email_id}: {status}")
                    continue

                for msg_part in email_data:
                    if isinstance(msg_part, tuple):
                        email_message = email.message_from_bytes(msg_part[1])
                        email_dict = parse_email(email_message, email_id.decode())
                        
                        # Save to database
                        storage.save_email_metadata(email_dict)
                        if email_dict.get("body"):
                            storage.save_email_body(email_dict.get("uid"), email_dict.get("body"))
                        
                        emails_saved += 1
            except Exception as e:
                print(f"Error processing email {email_id}: {e}")
                continue

        return emails_saved
    
    except Exception as e:
        print(f"Error fetching emails: {e}")
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
        
        # Extract attachment filenames using the same logic as download functions
        attachment_list = _extract_attachment_filenames(email_data)
        # Convert to comma-separated string for consistency with database storage
        attachments = ','.join(attachment_list)
        
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
            "body": body,
            "flagged": False,
            "attachments": attachments
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
            "body": body,
            "flagged": False,
            "attachments": []
        }

def _fetch_email_by_uid(mail, email_uid):
    """Helper function to fetch and parse an email by UID"""

    status, messages = mail.search(None, f"UID {email_uid}")
    if status != "OK" or not messages[0]:
        raise RuntimeError(f"Email with UID {email_uid} not found")
    
    status, email_data = mail.fetch(email_uid, "(RFC822)")
    if status != "OK":
        raise RuntimeError(f"Failed to fetch email {email_uid}")
    
    return email.message_from_bytes(email_data[0][1])

def _extract_attachment_filenames(email_message):
    """Helper function to extract just attachment filenames from an email message"""
    filenames = []
    
    for part in email_message.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        
        if "attachment" in content_disposition.lower():
            filename = part.get_filename()
            if filename:
                # Decode filename if needed (same logic as in _extract_attachments_from_email)
                decoded_filename = decode_header(filename)[0]
                if isinstance(decoded_filename[0], bytes):
                    filename = decoded_filename[0].decode(decoded_filename[1] or 'utf-8')
                else:
                    filename = decoded_filename[0]
                
                filenames.append(filename)
    
    return filenames

def _extract_attachments_from_email(email_message):
    """Helper function to extract attachment information from an email message"""
    attachments = []
    
    for part in email_message.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        
        if "attachment" in content_disposition.lower():
            filename = part.get_filename()
            if filename:
                # Decode filename if needed
                decoded_filename = decode_header(filename)[0]
                if isinstance(decoded_filename[0], bytes):
                    filename = decoded_filename[0].decode(decoded_filename[1] or 'utf-8')
                else:
                    filename = decoded_filename[0]
                
                # Get attachment content
                content = part.get_payload(decode=True)
                if content:
                    attachments.append({
                        'filename': filename,
                        'content': content
                    })
    
    return attachments

def _save_attachment_to_disk(filename, content, download_path):
    """Helper function to save attachment content to disk with duplicate handling"""
    import os
    
    # Create download directory if it doesn't exist
    os.makedirs(download_path, exist_ok=True)
    
    file_path = os.path.join(download_path, filename)
    
    # Handle duplicate filenames
    counter = 1
    original_file_path = file_path
    while os.path.exists(file_path):
        name, ext = os.path.splitext(original_file_path)
        file_path = f"{name}_{counter}{ext}"
        counter += 1
    
    # Save the file
    with open(file_path, 'wb') as f:
        f.write(content)
    
    return file_path

def download_all_attachments(config, email_uid, download_path="./attachments"):
    """Download all attachments from an email by UID"""
    mail = connect_to_imap(config)
    if not mail:
        raise RuntimeError("Failed to connect to IMAP server")
    
    try:
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
        
    finally:
        mail.close()
        mail.logout()

def download_attachment_by_index(config, email_uid, attachment_index, download_path="./attachments"):
    """Download a specific attachment from an email by UID and index"""
    mail = connect_to_imap(config)
    if not mail:
        raise RuntimeError("Failed to connect to IMAP server")
    
    try:
        email_message = _fetch_email_by_uid(mail, email_uid)
        attachments = _extract_attachments_from_email(email_message)
        
        if attachment_index >= len(attachments) or attachment_index < 0:
            raise RuntimeError(f"Invalid attachment index {attachment_index}. Available attachments: 0-{len(attachments)-1}")
        
        attachment = attachments[attachment_index]
        file_path = _save_attachment_to_disk(
            attachment['filename'], 
            attachment['content'], 
            download_path
        )
        return file_path
        
    finally:
        mail.close()
        mail.logout()

def get_attachment_list(config, email_uid):
    """Get list of attachment filenames from an email by UID without downloading"""
    mail = connect_to_imap(config)
    if not mail:
        raise RuntimeError("Failed to connect to IMAP server")
    
    try:
        email_message = _fetch_email_by_uid(mail, email_uid)
        return _extract_attachment_filenames(email_message)
        
    finally:
        mail.close()
        mail.logout()

def delete_email(config, email_uid):
    """Delete an email by UID from the server"""
    mail = connect_to_imap(config)
    if not mail:
        raise RuntimeError("Failed to connect to IMAP server")
    
    try:
        # Mark the email for deletion
        mail.uid('STORE', email_uid, '+FLAGS', r'(\Deleted)')
        mail.expunge()
        
    finally:
        mail.close()
        mail.logout()