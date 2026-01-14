"""Datetime parsing and validation utilities."""

import re
from datetime import datetime
from typing import Optional, Tuple

from src.utils.logging import get_logger

logger = get_logger(__name__)


class DateTimeParser:
    """Parse and validate date-time strings"""

    @staticmethod
    def parse_datetime(dt_str: str) -> Tuple[Optional[datetime], Optional[str]]:
        """Parse date-time string into datetime object"""
        if not dt_str or not dt_str.strip():
            return None, None

        dt_str = dt_str.strip()

        formats = [
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%d/%m/%Y %H:%M",
            "%m/%d/%Y %H:%M",
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(dt_str, fmt)

                if dt < datetime.now():
                    return None, f"Date-time '{dt_str}' is in the past."

                return dt, None

            except ValueError:
                continue

        try:
            dt = DateTimeParser._parse_natural_language(dt_str)
            if dt:
                if dt < datetime.now():
                    return None, f"Date-time '{dt_str}' is in the past."
                return dt, None

        except Exception as e:
            logger.warning(f"Failed to parse natural language date-time: {e}")

        return None, f"Invalid date-time format: '{dt_str}'."

    @staticmethod
    def _parse_natural_language(text: str) -> Optional[datetime]:
        """Parse basic natural language date-time strings"""
        from datetime import timedelta

        text = text.lower().strip()
        now = datetime.now()

        if "tomorrow" in text:
            base = now + timedelta(days=1)
            time_match = re.search(r"(\d{1,2}):?(\d{2})?\s*(am|pm)?", text)
            if time_match:
                hour = int(time_match.group(1))
                minute = int(time_match.group(2) or 0)
                ampm = time_match.group(3)

                if ampm == "pm" and hour < 12:
                    hour += 12
                elif ampm == "am" and hour == 12:
                    hour = 0

                return base.replace(hour=hour, minute=minute, second=0)

            else:
                return base.replace(hour=9, minute=0, second=0)

        hours_match = re.search(r"in\s+(\d+)\s+hours?", text)
        if hours_match:
            hours = int(hours_match.group(1))
            return now + timedelta(hours=hours)

        days_match = re.search(r"in\s+(\d+)\s+days?", text)
        if days_match:
            days = int(days_match.group(1))
            return now + timedelta(days=days)

        return None
