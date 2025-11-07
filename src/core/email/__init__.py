"""Email protocol handling - public API."""

from .parser import EmailParser
from .imap import IMAPClient
from .smtp import SMTPClient

__all__ = ['EmailParser', 'IMAPClient', 'SMTPClient']