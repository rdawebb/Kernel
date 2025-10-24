"""Attachment handling utilities for email attachments"""

import email
import os
import stat
import tempfile
from .log_manager import get_logger, log_call

logger = get_logger(__name__)

# Secure file permissions: owner can read/write, group/others have no access
SECURE_FILE_PERMS = stat.S_IRUSR | stat.S_IWUSR  # 0o600
SECURE_DIR_PERMS = stat.S_IRWXU  # 0o700

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
    """Save attachment to disk with atomic writes, duplicate handling, and secure permissions.
    
    Returns:
        str: Path to saved file on success
        None: On failure (all errors logged gracefully)
    """
    # Validate filename to prevent path traversal attacks
    if os.path.sep in filename or ".." in filename:
        logger.error(f"Invalid filename detected: {filename}")
        return None
    
    try:
        os.makedirs(download_path, exist_ok=True)
        # Set secure permissions on directory (owner-only access)
        os.chmod(download_path, SECURE_DIR_PERMS)
    except OSError as e:
        logger.error(f"Failed to create download directory {download_path}: {e}")
        return None
    
    file_path = os.path.join(download_path, filename)
    
    counter = 1
    original_file_path = file_path
    while os.path.exists(file_path):
        name, ext = os.path.splitext(original_file_path)
        file_path = f"{name}_{counter}{ext}"
        counter += 1
    
    # Use atomic write: write to temporary file first, then move to final location
    temp_fd = None
    temp_file_path = None
    try:
        # Create temporary file in the same directory to ensure atomic rename
        temp_fd, temp_file_path = tempfile.mkstemp(dir=download_path)
        
        # Write content to temp file
        try:
            os.write(temp_fd, content)
        finally:
            os.close(temp_fd)
            temp_fd = None
        
        # Set secure permissions on the temporary file before renaming
        os.chmod(temp_file_path, SECURE_FILE_PERMS)
        
        # Atomic rename to final location
        os.replace(temp_file_path, file_path)
        logger.info(f"Attachment saved atomically with secure permissions: {file_path}")
        return file_path
        
    except (OSError, IOError) as e:
        logger.error(f"Failed to write attachment to {file_path}: {e}")
        # Clean up temp file if it exists
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.debug(f"Cleaned up temporary file: {temp_file_path}")
            except OSError as cleanup_err:
                logger.warning(f"Failed to clean up temp file {temp_file_path}: {cleanup_err}")
        return None
    except Exception as e:
        # Catch any other unexpected errors
        logger.error(f"Unexpected error saving attachment: {e}")
        if temp_fd is not None:
            try:
                os.close(temp_fd)
            except OSError:
                pass
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except OSError:
                pass
        return None

@log_call
def _fetch_email_by_uid(mail, email_uid):
    """Fetch and parse email message by UID."""

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

@log_call
def download_attachments(account_config, email_uid, attachment_index=None, download_path="./attachments"):
    """Download attachments from email by UID."""
    from src.core.imap_client import imap_connection

    with imap_connection(account_config) as mail:
        if not mail:
            return []
            
        email_message = _fetch_email_by_uid(mail, email_uid)
        if not email_message:
            return []
            
        attachments = _extract_attachments(email_message, include_content=True)

        if not attachments:
            logger.error(f"No attachments found for email {email_uid}")
            print("No attachments found. Please check and try again.")
            return []

        # Filter attachments based on index parameter
        if attachment_index is not None:
            if attachment_index >= len(attachments) or attachment_index < 0:
                logger.error(f"Invalid attachment index {attachment_index}. Available attachments: 0-{len(attachments)-1}")
                print("Invalid attachment index. Please check and try again.")
                return []
            attachments = [attachments[attachment_index]]

        # Download filtered attachments
        downloaded_files = []
        failed_count = 0
        for attachment in attachments:
            try:
                file_path = _save_attachment_to_disk(
                    attachment['filename'], 
                    attachment['content'], 
                    download_path
                )
                if file_path:
                    downloaded_files.append(file_path)
                    logger.info(f"Successfully saved attachment to: {file_path}")
                else:
                    failed_count += 1
                    logger.warning(f"Failed to save attachment '{attachment['filename']}'")
            except Exception as e:
                failed_count += 1
                logger.error(f"Unexpected error saving attachment '{attachment['filename']}': {e}")
                continue
        
        if failed_count > 0:
            logger.warning(f"Successfully downloaded {len(downloaded_files)} attachment(s), but {failed_count} failed")
        
        return downloaded_files

@log_call
def get_attachment_list(account_config, email_uid):
    """Get attachment filenames from email without downloading."""
    from src.core.imap_client import imap_connection

    with imap_connection(account_config) as mail:
        if not mail:
            return []
            
        email_message = _fetch_email_by_uid(mail, email_uid)
        if not email_message:
            return []
        
        attachments = _extract_attachments(email_message, include_content=False)
        return [att['filename'] for att in attachments]
