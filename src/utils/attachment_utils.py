"""Attachment handling utilities for email attachments"""

import email
import os
from . import log_manager


def _extract_attachments(email_message, include_content=True):
    """Extract attachment info from email message."""
    from .email_parser import decode_filename
    
    attachments = []
    
    for part in email_message.walk():
        content_disposition = str(part.get("Content-Disposition", ""))
        
        if "attachment" in content_disposition.lower():
            filename = part.get_filename()
            if filename:
                decoded_filename = decode_filename(filename)
                attachment = {'filename': decoded_filename}
                
                if include_content:
                    content = part.get_payload(decode=True)
                    if content:
                        attachment['content'] = content
                
                attachments.append(attachment)
    
    return attachments


def _save_attachment_to_disk(filename, content, download_path):
    """Save attachment to disk with duplicate handling."""
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


def _fetch_email_by_uid(mail, email_uid):
    """Fetch and parse email message by UID."""

    status, messages = mail.search(None, f"UID {email_uid}")
    if status != "OK" or not messages[0]:
        log_manager.error(f"Email with UID {email_uid} not found")
        print("Sorry, unable to find this email. Please check your settings or try again.")
        return None

    status, email_data = mail.fetch(email_uid, "(RFC822)")
    if status != "OK":
        log_manager.error(f"Failed to fetch email {email_uid}")
        print("Sorry, failed to fetch email. Please check your settings or try again.")
        return None
    
    return email.message_from_bytes(email_data[0][1])


def download_attachments(config, email_uid, attachment_index=None, download_path="./attachments"):
    """Download attachments from email by UID."""
    from src.core.imap_client import imap_connection
    
    with imap_connection(config) as mail:
        if not mail:
            return []
            
        email_message = _fetch_email_by_uid(mail, email_uid)
        if not email_message:
            return []
            
        attachments = _extract_attachments(email_message, include_content=True)

        if not attachments:
            log_manager.error(f"No attachments found for email {email_uid}")
            print("No attachments found. Please check and try again.")
            return []

        # Filter attachments based on index parameter
        if attachment_index is not None:
            if attachment_index >= len(attachments) or attachment_index < 0:
                log_manager.error(f"Invalid attachment index {attachment_index}. Available attachments: 0-{len(attachments)-1}")
                print("Invalid attachment index. Please check and try again.")
                return []
            attachments = [attachments[attachment_index]]

        # Download filtered attachments
        downloaded_files = []
        for attachment in attachments:
            file_path = _save_attachment_to_disk(
                attachment['filename'], 
                attachment['content'], 
                download_path
            )
            downloaded_files.append(file_path)
        
        return downloaded_files


def get_attachment_list(config, email_uid):
    """Get attachment filenames from email without downloading."""
    from src.core.imap_client import imap_connection
    
    with imap_connection(config) as mail:
        if not mail:
            return []
            
        email_message = _fetch_email_by_uid(mail, email_uid)
        if not email_message:
            return []
        
        attachments = _extract_attachments(email_message, include_content=False)
        return [att['filename'] for att in attachments]
