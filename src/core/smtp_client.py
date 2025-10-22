"""SMTP client for sending emails via an SMTP server"""

## TODO: refactor to improve error handling and logging, add support for HTML emails and attachments
## TODO: Check logging and error handling in all functions
## TODO: add retry logic for transient errors
## TODO: add CC and BCC support

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from contextlib import contextmanager
from ..utils.config_manager import ConfigManager
from ..utils.log_manager import get_logger, log_call

logger = get_logger(__name__)
config_manager = ConfigManager()

@contextmanager
def smtp_connection():
    """Context manager for SMTP connections with automatic cleanup"""
    server = None
    try:
        smtp_server = config_manager.get_config('account.smtp_server')
        smtp_port = config_manager.get_config('account.smtp_port', 587)
        use_tls = config_manager.get_config('account.use_tls', True)
        email = config_manager.get_config('account.email')
        password = config_manager.get_config('account.password')
        
        if use_tls:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port)
            server.starttls()

        server.login(email, password)
        logger.info(f"Connected to SMTP server {smtp_server}:{smtp_port}")
        yield server
    
    except Exception as e:
        logger.error(f"Failed to connect to SMTP server: {e}")
        print("Unable to connect to the SMTP server. Please check your configuration and try again.")
        yield None

    finally:
        if server:
            try:
                server.quit()
            except Exception:
                pass

@log_call
def send_email(to_email=None, subject="Test Email from tui_mail", body="This is a test email sent from the tui_mail SMTP client.", cc=None, bcc=None):
    """
    Send an email via SMTP
    
    Args:
        to_email (str): Recipient email address (defaults to self)
        subject (str): Email subject
        body (str): Email body text
        cc (list): List of CC recipients
        bcc (list): List of BCC recipients
    """
    try:
        email_from = config_manager.get_config('account.email')
        
        if not to_email:
            to_email = email_from
        
        msg = MIMEMultipart()
        msg['From'] = email_from
        msg['To'] = to_email
        msg['Subject'] = subject
        
        if cc:
            msg['Cc'] = ', '.join(cc) if isinstance(cc, list) else cc
        if bcc:
            msg['Bcc'] = ', '.join(bcc) if isinstance(bcc, list) else bcc
        
        msg.attach(MIMEText(body, 'plain'))

        with smtp_connection() as server:
            if server is None:
                logger.error("SMTP server connection is None, email not sent")
                print("Unable to send email due to SMTP connection issues. Please check your configuration and try again.")
                return False
            recipients = [to_email]
            if cc:
                recipients.extend(cc if isinstance(cc, list) else [cc])
            if bcc:
                recipients.extend(bcc if isinstance(bcc, list) else [bcc])
            
            server.send_message(msg, to_addrs=recipients)
            logger.info(f"Email sent to {to_email}")
            return True
    
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        print("Unable to send email. Please check your configuration and try again.")
        return False
