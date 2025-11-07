"""Unified attachments handling module."""

import os
import platform
import stat
import subprocess
from email import message_from_bytes
from email.message import Message
from pathlib import Path
from typing import List, Optional, Tuple

from src.utils.errors import (
    AttachmentDownloadError,
    AttachmentNotFoundError,
    FileSystemError,
    InvalidPathError,
    KernelError,
)
from src.utils.logging import get_logger
from src.utils.paths import ATTACHMENTS_DIR
from src.utils.security import PathSecurity

logger = get_logger(__name__)

SECURE_DIR_PERMS = stat.S_IRWXU  # Owner-only access


class AttachmentManager:
    """Manage all email attachment operations."""

    def __init__(self, config_manager=None):
        """Initialize attachment manager with config."""

        self.config_manager = config_manager
        self._attachments_dir = None


    def get_attachments_dir(self) -> Path:
        """Get or create the attachments directory with secure permissions."""
        
        if self._attachments_dir is None:
            if self.config_manager:
                path_str = self.config_manager.config.database.attachments_path
                self._attachments_dir = Path(os.path.expanduser(path_str))
            else:
                self._attachments_dir = ATTACHMENTS_DIR

        return self._attachments_dir
    

    def ensure_attachments_dir(self) -> Path:
        """Ensure the attachments directory exists with secure permissions."""
        
        attachments_dir = self.get_attachments_dir()
        
        try:
            attachments_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(attachments_dir, SECURE_DIR_PERMS)
            logger.debug(f"Attachments directory ready: {attachments_dir}")
            return attachments_dir
        
        except OSError as e:
            raise FileSystemError("Failed to create attachments directory") from e
        

    ## Attachment Extraction

    def extract_attachments_from_email(self, email_message: Message) -> List[Tuple[str, bytes]]:
        """Extract attachments from an email message."""
        
        attachments = []
        
        for part in email_message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue
            
            filename = part.get_filename()
            if not filename:
                continue
            
            filename = self._sanitize_filename(filename)

            try:
                content = part.get_payload(decode=True)
                if content:
                    attachments.append((filename, content))
                    logger.debug(f"Extracted attachment: {filename}")
            
            except Exception as e:
                raise AttachmentDownloadError(f"Failed to extract attachment {filename}") from e

        return attachments
    

    def get_attachment_list_from_email(self, email_message: Message) -> List[str]:
        """Get a list of attachment filenames from an email message."""
        
        filenames = []

        for part in email_message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue
            
            filename = part.get_filename()
            if filename:
                filenames.append(self._sanitize_filename(filename))

        return filenames
        
        
    ## Downloading Attachments

    def download_from_email_data(self, email_data: dict,
                                 attachment_index: Optional[int] = None) -> List[Path]:
        """Download attachments from email data dictionary."""

        try:
            if "raw_email" in email_data:
                email_message = message_from_bytes(email_data["raw_email"])
            else:
                from email.mime.text import MIMEText
                email_message = MIMEText(email_data.get("body", ""), "plain")

            attachments = self.extract_attachments_from_email(email_message)

            if not attachments:
                logger.info("No attachments found in email.")
                return []
            
            if attachment_index is not None:
                if 0 <= attachment_index < len(attachments):
                    attachments = [attachments[attachment_index]]
                else:
                    raise InvalidPathError(f"Invalid attachment index {attachment_index} (email has {len(attachments)} attachments)")
                
            return self._save_attachments(attachments, email_data.get("uid", "unknown"))
        
        except KernelError:
            raise
        
        except Exception as e:
            raise AttachmentDownloadError("Failed to download attachments from email data") from e
    

    def download_from_imap(self, imap_client, email_uid: str,
                           attachment_index: Optional[int] = None) -> List[Path]:
        """Download attachments directly from IMAP server."""

        try:
            status, email_data = imap_client.uid('fetch', email_uid, '(RFC822)')

            if status != 'OK' or not email_data or email_data[0] is None:
                raise AttachmentDownloadError(f"Failed to fetch email UID {email_uid} from IMAP server")
            
            email_message = message_from_bytes(email_data[0][1])
            attachments = self.extract_attachments_from_email(email_message)

            if not attachments:
                logger.info(f"No attachments found in email UID {email_uid}.")
                return []
            
            if attachment_index is not None:
                if 0 <= attachment_index < len(attachments):
                    attachments = [attachments[attachment_index]]
                else:
                    raise InvalidPathError(f"Invalid attachment index {attachment_index} (email has {len(attachments)} attachments)")
                
            return self._save_attachments(attachments, email_uid)
        
        except KernelError:
            raise
        
        except Exception as e:
            raise AttachmentDownloadError(f"Failed to download attachments from email UID {email_uid}") from e
        
    
    def _save_attachments(self, attachments: List[Tuple[str, bytes]],
                          email_uid: str) -> List[Path]:
        """Save attachments to the attachments directory."""
        
        attachments_dir = self.ensure_attachments_dir()

        email_dir = attachments_dir / str(email_uid)
        email_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(str(email_dir), SECURE_DIR_PERMS)

        saved_files = []

        for filename, content in attachments:
            try:
                file_path = email_dir / filename

                with open(file_path, 'wb') as f:
                    f.write(content)

                os.chmod(str(file_path), stat.S_IRUSR | stat.S_IWUSR)

                saved_files.append(file_path)
                logger.info(f"Saved attachment to {file_path}")

            except OSError as e:
                raise FileSystemError(f"Failed to save attachment {filename}") from e
            except Exception as e:
                raise AttachmentDownloadError(f"Failed to save attachment {filename}") from e

        return saved_files
    

    ## Listing Attachments

    def list_downloaded_attachments(self) -> List[Tuple[Path, int]]:
        """List all downloaded attachments with file sizes."""

        attachments_dir = self.get_attachments_dir()
        
        if not attachments_dir.exists():
            logger.info("No attachments directory found.")
            return []
        
        files = []

        try:
            for file_path in attachments_dir.rglob('*'):
                if file_path.is_file():
                    try:
                        size = file_path.stat().st_size
                        files.append((file_path, size))
                    
                    except OSError as e:
                        logger.warning(f"Failed to get size for {file_path}: {e}")

            files.sort(key=lambda x: x[0].stat().st_mtime, reverse=True)
        
        except Exception as e:
            raise FileSystemError("Failed to list downloaded attachments") from e

        return files

        
    def get_attachment_list_for_email(self, email_uid: str) -> List[str]:
        """Get list of attachment filenames for a specific email UID."""
        
        attachments_dir = self.get_attachments_dir()
        email_dir = attachments_dir / str(email_uid)

        if not email_dir.exists():
            logger.info(f"No attachments found for email UID {email_uid}.")
            return []
        
        try:
            return [f.name for f in email_dir.iterdir() if f.is_file()]
        
        except Exception as e:
            raise AttachmentNotFoundError(f"Failed to get attachment list for email UID {email_uid}") from e
    

    ## Opening Attachments

    def open_attachment(self, filename: str) -> bool:
        """Open an attachment file using the default system application."""
        
        if not self._is_safe_filename(filename):
            raise InvalidPathError(f"Invalid filename: {filename}")
        
        attachments_dir = self.get_attachments_dir()
        file_path = attachments_dir / filename

        if not file_path.exists() or not file_path.is_file():
            raise AttachmentNotFoundError(f"File not found: {file_path}")
        
        try:
            file_path.resolve().relative_to(attachments_dir.resolve())
        
        except ValueError:
            raise InvalidPathError(f"File outside attachments directory: {filename}")
        
        try:
            if platform.system() == "Darwin":
                subprocess.run(["open", str(file_path)], check=True)
            elif platform.system() == "Windows":
                os.startfile(str(file_path))
            else:
                subprocess.run(["xdg-open", str(file_path)], check=True)

            logger.info(f"Opened attachment: {file_path}")
            return True
        
        except subprocess.CalledProcessError as e:
            raise AttachmentDownloadError(f"Failed to open attachment {file_path}") from e
        
        except FileNotFoundError as e:
            raise AttachmentDownloadError(f"No application found to open attachment {file_path}") from e
        
        except Exception as e:
            raise AttachmentDownloadError(f"Error opening attachment {file_path}") from e
        
    
    ## Utility Methods

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent directory traversal."""

        return PathSecurity.sanitize_filename(filename)


    def _is_safe_filename(self, filename: str) -> bool:
        """Check if the filename is safe (no directory traversal)."""
        
        return PathSecurity.validate_filename(filename)
    

    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in human-readable form."""
        
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 ** 2:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024 ** 3:
            return f"{size_bytes / (1024 ** 2):.2f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.2f} GB"
