import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from contextlib import contextmanager
from quiet_mail.utils.config import load_config

@contextmanager
def smtp_connection():
    """Context manager for SMTP connections with automatic cleanup"""
    config = load_config()
    server = None
    try:
        if config['smtp_use_ssl']:
            server = smtplib.SMTP_SSL(config['smtp_server'], config['smtp_port'])
        else:
            server = smtplib.SMTP(config['smtp_server'], config['smtp_port'])
            server.starttls()

        server.login(config['email'], config['password'])
        yield server
    
    except Exception as e:
        raise RuntimeError(f"Failed to connect to SMTP server: {e}")
    
    finally:
        if server:
            server.quit()

def send_email(to_email=None, subject="Test Email from quiet_mail", body="This is a test email sent from the quiet_mail SMTP client.", cc=None, bcc=None):
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
        config = load_config()
        
        # Default to sending to self if no recipient specified
        if not to_email:
            to_email = config['email']
        
        msg = MIMEMultipart()
        msg['From'] = config['email']
        msg['To'] = to_email
        msg['Subject'] = subject
        
        if cc:
            msg['Cc'] = ', '.join(cc) if isinstance(cc, list) else cc
        if bcc:
            msg['Bcc'] = ', '.join(bcc) if isinstance(bcc, list) else bcc
        
        msg.attach(MIMEText(body, 'plain'))

        # Send the email using context manager
        with smtp_connection() as server:
            recipients = [to_email]
            if cc:
                recipients.extend(cc if isinstance(cc, list) else [cc])
            if bcc:
                recipients.extend(bcc if isinstance(bcc, list) else [bcc])
            
            server.send_message(msg, to_addrs=recipients)
            return True
    
    except Exception as e:
        raise RuntimeError(f"Failed to send email: {e}")