"""SMTP client for sending emails via an SMTP server"""

## TODO: add support for HTML emails and attachments

import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Tuple
from src.utils.log_manager import get_logger
from src.utils.error_handling import AuthenticationError, NetworkError, SMTPError

logger = get_logger(__name__)


TRANSIENT_ERRORS = [
    421, # Service not available, closing transmission channel
    450, # Requested mail action not taken: mailbox unavailable
    451, # Requested action aborted: local error in processing
    452, # Requested action not taken: insufficient system storage
    454, # Temporary authentication failure
]

class SMTPClient:
    """SMTP client with connection pooling and retry logic."""
    
    def __init__(self, host: str, port: int, username: str, password: str, 
                 use_tls: bool = True, max_retries: int = 3, retry_delay: float = 2.0):
        """Initialize SMTP client."""

        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.server = None
        self.last_used = time.time()
        self.logger = get_logger(__name__)
    

    def _connect(self) -> bool:
        """Establish connection to SMTP server."""

        try:
            if self.use_tls:
                self.server = smtplib.SMTP_SSL(self.host, self.port)
            else:
                self.server = smtplib.SMTP(self.host, self.port)
                self.server.starttls()
            
            self.server.login(self.username, self.password)
            self.logger.info(f"Connected to SMTP server {self.host}:{self.port}")
            self.last_used = time.time()
            return True
        
        except smtplib.SMTPAuthenticationError as e:
            self.logger.error(f"SMTP authentication failed: {e}")
            raise AuthenticationError(
                "SMTP authentication failed",
                details={"host": self.host, "username": self.username, "error": str(e)}
            ) from e
        
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected) as e:
            self.logger.error(f"SMTP connection error: {e}")
            raise NetworkError(
                "Failed to connect to SMTP server",
                details={"host": self.host, "port": self.port, "error": str(e)}
            ) from e

        except Exception as e:
            self.logger.error(f"Failed to connect to SMTP server: {e}")
            raise SMTPError(
                "Failed to connect to SMTP server",
                details={"host": self.host, "port": self.port, "error": str(e)}
            ) from e
        
    
    def _ensure_connected(self) -> bool:
        """Ensure connection is active, reconnect if needed."""

        if self.server is None:
            return self._connect()
        
        try:
            self.server.noop()
            return True
        
        except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError):
            self.logger.warning("SMTP connection lost, reconnecting...")
            self.server = None
            return self._connect()
        
    
    def _is_transient_error(self, error: smtplib.SMTPException) -> bool:
        """Check if an SMTP error is transient based on its code."""
        
        if isinstance(error, smtplib.SMTPResponseException):
            return error.smtp_code in TRANSIENT_ERRORS

        if isinstance(error, (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError)):
            return True
        
        return False
    

    def send_email(self, to_email: str, subject: str, body: str, 
                   cc: Optional[List[str]] = None, 
                   bcc: Optional[List[str]] = None) -> Tuple[bool, Optional[str]]:
        """Send an email via SMTP with retry logic for transient errors."""

        attempt = 0
        last_error = None

        while attempt <= self.max_retries:
            try:
                if not self._ensure_connected():
                    raise SMTPError("Unable to connect to SMTP server")
                
                msg = MIMEMultipart()
                msg['From'] = self.username
                msg['To'] = to_email
                msg['Subject'] = subject
                
                if cc:
                    msg['Cc'] = ', '.join(cc) if isinstance(cc, list) else cc
                if bcc:
                    msg['Bcc'] = ', '.join(bcc) if isinstance(bcc, list) else bcc
                
                msg.attach(MIMEText(body, 'plain'))
                
                recipients = [to_email]
                if cc:
                    recipients.extend(cc if isinstance(cc, list) else [cc])
                if bcc:
                    recipients.extend(bcc if isinstance(bcc, list) else [bcc])
                
                self.server.send_message(msg, to_addrs=recipients)
                self.logger.info(f"Email sent to {to_email}")
                self.last_used = time.time()
                return True, None
            
            except smtplib.SMTPException as e:
                last_error = e
                attempt += 1

                if self._is_transient_error(e):
                    if attempt < self.max_retries:
                        delay = self.retry_delay * (2 ** (attempt - 1))
                        self.logger.warning(f"Transient SMTP error occurred: {e}, retrying in {delay} seconds")
                        time.sleep(delay)
                        self.close()
                        continue
                    else:
                        self.logger.error(f"Max retries {self.max_retries} exceeded: {e}")
                
                else:
                    self.logger.error(f"Non-transient SMTP error occurred: {e}")
                    break
                        
            except Exception as e:
                self.logger.error(f"Unexpected error sending email: {e}")
                last_error = e
                break

        error_msg = f"Failed to send after {attempt} attempt(s): {str(last_error)}"
        self.logger.error(error_msg)
        return False, error_msg
    

    def close(self) -> None:
        """Close SMTP connection."""

        if self.server:
            try:
                self.server.quit()
                self.logger.debug("SMTP connection closed")

            except Exception:
                pass

            finally:
                self.server = None
    

    def __del__(self):
        """Cleanup on deletion."""

        self.close()
