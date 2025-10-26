"""SMTP client for sending emails via an SMTP server"""

## TODO: add support for HTML emails and attachments
## TODO: add retry logic for transient errors

import smtplib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from ..utils.config_manager import ConfigManager
from ..utils.log_manager import get_logger

logger = get_logger(__name__)


class SMTPClient:
    """SMTP client for sending emails with connection pooling."""
    
    def __init__(self, host: str, port: int, username: str, password: str, use_tls: bool = True):
        """
        Initialize SMTP client.
        
        Args:
            host: SMTP server hostname
            port: SMTP server port
            username: Email username
            password: Email password
            use_tls: Whether to use TLS encryption
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.use_tls = use_tls
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
        
        except Exception as e:
            self.logger.error(f"Failed to connect to SMTP server: {e}")
            print("Unable to connect to the SMTP server. Please check your configuration and try again.")
            return False
    
    def _ensure_connected(self) -> bool:
        """Ensure connection is active, reconnect if needed."""
        if self.server is None:
            return self._connect()
        return True
    
    def send_email(self, to_email: str, subject: str, body: str, cc: Optional[List[str]] = None, bcc: Optional[List[str]] = None) -> bool:
        """
        Send an email via SMTP.
        
        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body text
            cc: List of CC recipients
            bcc: List of BCC recipients
            
        Returns:
            True if email sent successfully, False otherwise
        """
        try:
            if not self._ensure_connected():
                return False
            
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
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to send email: {e}")
            print("Unable to send email. Please check your configuration and try again.")
            return False
    
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


# Legacy function-based interface for backwards compatibility
def send_email(to_email=None, subject="Test Email from tui_mail", body="This is a test email sent from the tui_mail SMTP client.", cc=None, bcc=None):
    """
    Send an email via SMTP (legacy function-based interface).
    
    Args:
        to_email (str): Recipient email address (defaults to self)
        subject (str): Email subject
        body (str): Email body text
        cc (list): List of CC recipients
        bcc (list): List of BCC recipients
    """
    config_manager = ConfigManager()
    
    try:
        email_from = config_manager.get_config('account.email')
        
        if not to_email:
            to_email = email_from
        
        smtp_server = config_manager.get_config('account.smtp_server')
        smtp_port = config_manager.get_config('account.smtp_port', 587)
        use_tls = config_manager.get_config('account.use_tls', True)
        password = config_manager.get_config('account.password')
        
        client = SMTPClient(
            host=smtp_server,
            port=smtp_port,
            username=email_from,
            password=password,
            use_tls=use_tls
        )
        
        result = client.send_email(to_email, subject, body, cc, bcc)
        client.close()
        return result
    
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        print("Unable to send email. Please check your configuration and try again.")
        return False
