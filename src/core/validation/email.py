"""Email validation utilities."""

import re
from typing import Any, Dict, Optional, Tuple

from src.utils.errors import InvalidEmailAddressError, ValidationError
from src.utils.logging import get_logger

logger = get_logger(__name__)


class EmailValidator:
    """Validate email addresses and content"""

    @staticmethod
    def is_valid_email(email_address: str) -> bool:
        """Validate email address format"""
        if not email_address or not isinstance(email_address, str):
            return False
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

        return bool(re.match(pattern, email_address.strip()))
    
    @staticmethod
    def validate_email_dict(email_dict: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate structured email dictionary"""
        required_fields = ["uid", "subject", "sender", "recipient", "body"]

        for field in required_fields:
            if field not in email_dict:
                raise ValidationError(f"Missing required field: {field}")
            
            if not email_dict[field] and field != "body":
                raise ValidationError(f"Field '{field}' cannot be empty")
            
        if not EmailValidator.is_valid_email(email_dict["sender"]):
            raise InvalidEmailAddressError(
                f"Invalid sender email address: {email_dict['sender']}"
            )

        if not EmailValidator.is_valid_email(email_dict["recipient"]):
            raise InvalidEmailAddressError(
                f"Invalid recipient email address: {email_dict['recipient']}"
            )

        return True, None