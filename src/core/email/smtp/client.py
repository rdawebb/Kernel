"""SMTP client for high-level email operations."""

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List, Optional

from src.utils.logging import async_log_call, get_logger

from .protocol import SMTPProtocol

logger = get_logger(__name__)


class SMTPClient:
    """High-level SMTP email operations."""

    def __init__(self, protocol: SMTPProtocol, sender_email: str):
        """Initialise SMTP client.

        Args:
            protocol: SMTPProtocol instance for low-level operations
            sender_email: Default sender email address
        """
        self.protocol = protocol
        self.sender_email = sender_email

    def _create_message(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        html_body: Optional[str] = None,
    ) -> MIMEMultipart:
        """Create MIME message from components.

        Args:
            to_email: Primary recipient
            subject: Email subject
            body: Plain text body
            cc: Optional CC recipients
            bcc: Optional BCC recipients
            html_body: Optional HTML body

        Returns:
            Constructed MIME message
        """
        msg = MIMEMultipart("alternative" if html_body else "mixed")
        msg["From"] = self.sender_email
        msg["To"] = to_email
        msg["Subject"] = subject

        if cc:
            msg["Cc"] = ", ".join(cc)
        if bcc:
            msg["Bcc"] = ", ".join(bcc)

        msg.attach(MIMEText(body, "plain"))

        if html_body:
            msg.attach(MIMEText(html_body, "html"))

        return msg

    def _get_all_recipients(
        self,
        to_email: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> List[str]:
        """Get complete list of recipients.

        Args:
            to_email: Primary recipient
            cc: Optional CC recipients
            bcc: Optional BCC recipients

        Returns:
            List of all recipient email addresses
        """
        recipients = [to_email]
        if cc:
            recipients.extend(cc if isinstance(cc, list) else [cc])
        if bcc:
            recipients.extend(bcc if isinstance(bcc, list) else [bcc])
        return recipients

    @async_log_call
    async def send_text_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """Send a plain text email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body text
            cc: Optional CC recipients
            bcc: Optional BCC recipients

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            message = self._create_message(to_email, subject, body, cc, bcc)
            recipients = self._get_all_recipients(to_email, cc, bcc)

            result = await self.protocol.send_message(message, recipients)

            if result:
                logger.info(f"Email sent to {to_email}")

            return result

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    @async_log_call
    async def send_html_email(
        self,
        to_email: str,
        subject: str,
        text_body: str,
        html_body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """Send an HTML email with plain text fallback.

        Args:
            to_email: Recipient email address
            subject: Email subject
            text_body: Plain text body (fallback)
            html_body: HTML body
            cc: Optional CC recipients
            bcc: Optional BCC recipients

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            message = self._create_message(
                to_email, subject, text_body, cc, bcc, html_body
            )
            recipients = self._get_all_recipients(to_email, cc, bcc)

            result = await self.protocol.send_message(message, recipients)

            if result:
                logger.info(f"HTML email sent to {to_email}")

            return result

        except Exception as e:
            logger.error(f"Failed to send HTML email to {to_email}: {e}")
            return False

    @async_log_call
    async def send_email_with_attachments(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachments: List[Path],
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
    ) -> bool:
        """Send email with file attachments.

        Args:
            to_email: Recipient email address
            subject: Email subject
            body: Email body text
            attachments: List of file paths to attach
            cc: Optional CC recipients
            bcc: Optional BCC recipients

        Returns:
            True if sent successfully, False otherwise
        """
        try:
            message = self._create_message(to_email, subject, body, cc, bcc)

            for file_path in attachments:
                if not file_path.exists():
                    logger.warning(f"Attachment not found: {file_path}")
                    continue

                with open(file_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f"attachment; filename= {file_path.name}",
                    )
                    message.attach(part)

            recipients = self._get_all_recipients(to_email, cc, bcc)
            result = await self.protocol.send_message(message, recipients)

            if result:
                logger.info(
                    f"Email with {len(attachments)} attachments sent to {to_email}"
                )

            return result

        except Exception as e:
            logger.error(f"Failed to send email with attachments to {to_email}: {e}")
            return False
