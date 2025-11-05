"""Interactive email composer - orchestrates UI, logic, and utilities"""

import asyncio
from typing import Optional

from rich.console import Console

from src.core.database import get_database
from src.core.email_handling import EmailComposer, EmailValidator
from src.utils.config_manager import ConfigManager
from src.utils.console import get_console
from src.utils.log_manager import async_log_call, get_logger
from src.utils.ui_helpers import confirm_action
from .composer_ui import (
    prompt_email_details,
    prompt_send_later,
    show_draft_saved,
    show_email_preview,
    show_send_failed,
    show_send_scheduled,
    show_send_success,
)

logger = get_logger(__name__)


@async_log_call
async def compose_email(console: Optional[Console] = None) -> bool:
    """Main function to compose and send an email interactively"""
    output_console = console or get_console()
    
    try:
        config = ConfigManager()
        composer = EmailComposer(config=config)
        db = get_database(config)

    except Exception as e:
        logger.error(f"Failed to initialize composer: {e}")
        await show_send_failed(f"Failed to initialize composer: {e}", console=output_console)
        return False

    try:
        email_details = await prompt_email_details(console=output_console)
        if not email_details:
            return False
    
        email_data = composer.create_email_dict(
            recipient=email_details["recipient"],
            subject=email_details["subject"],
            body=email_details["body"]
        )
    
        try:
            EmailValidator.validate_email_dict(email_data)
    
        except Exception as e:
            logger.error(f"Validation failed: {e}")
            await show_send_failed(f"Validation failed: {e}", console=output_console)
            return False

        await show_email_preview(email_data, console=output_console)

        if not await confirm_action("Send this email?", console=output_console):
            logger.info("Email cancelled - saved as draft")
            await show_draft_saved(console=output_console)
        
            try:
                await db.save_email("drafts", email_data)
        
            except Exception as e:
                logger.error(f"Failed to save draft: {e}")
                await show_send_failed(f"Failed to save draft: {e}", console=output_console)
        
            return False
    
        send_time = await prompt_send_later(console=output_console)

        if send_time:
            success, error = await composer.schedule_email(email_data, send_time)

            if success:
                await show_send_scheduled(send_time, console=output_console)
                return True
            else:
                await show_send_failed(error, console=output_console)
                return False
        else:
            try:
                success, error = await asyncio.to_thread(
                    composer.send_email,
                    to_email=email_data["recipient"],
                    subject=email_data["subject"],
                    body=email_data["body"],
                )

                if success:
                    await show_send_success(email_data, console=output_console)
                    return True
                else:
                    await show_send_failed(error, console=output_console)
                    return False
            
            except Exception as e:
                logger.error(f"Failed to send email: {e}")
                await show_send_failed(f"Failed to send email: {e}", console=output_console)
                return False
        
    except Exception as e:
        logger.error(f"Unexpected error during email composition: {e}")
        await show_send_failed(f"Unexpected error during email composition: {e}", console=output_console)
        return False