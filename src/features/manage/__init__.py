"""Email management feature (delete, move, flag, etc).

Public API:
    delete_email(email_id, folder, permanent)
    move_email(email_id, from_folder, to_folder)
    flag_email(email_id, folder)
    unflag_email(email_id, folder)
"""

from .workflow import delete_email, move_email, flag_email, unflag_email, ManageWorkflow

__all__ = ["delete_email", "move_email", "flag_email", "unflag_email", "ManageWorkflow"]
