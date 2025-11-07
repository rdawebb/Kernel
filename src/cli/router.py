"""Routes CLI commands to feature modules."""

from typing import Any, Callable, Dict, Optional

from rich.console import Console

from src.features.compose import compose_email
from src.features.view import view_email, view_folder, EmailFilters
from src.features.search import search_emails
from src.features.manage import delete_email, move_email, flag_email, unflag_email
from src.features.attachments import (
    list_attachments,
    download_attachment,
    download_all_attachments,
    list_downloads,
    open_attachment
)
from src.features.sync import sync_emails
from src.features.maintenance import backup_database, export_emails, delete_database
from src.utils.logging import async_log_call, get_logger

logger = get_logger(__name__)


class CommandRouter:
    """Routes commands to appropriate feature workflows."""
    
    def __init__(self, console: Optional[Console] = None):
        self.console = console
    
    @async_log_call
    async def route(self, command: str, args: Optional[Dict[str, Any]] = None) -> bool:
        """Route command to feature.
        
        Args:
            command: Command name
            args: Parsed arguments dictionary
            
        Returns:
            True if command executed successfully
            
        Raises:
            ValueError: If command is unknown
        """
        if args is None:
            args = {}

        if not isinstance(command, str):
            raise TypeError("First argument to route() must be a command string")
        if not isinstance(args, dict):
            raise TypeError("Second argument to route() must be a dict")
    
        handler = self._get_handler(command, args)
        if not handler:
            raise ValueError(f"Unknown command: {command}")
        
        try:
            return await handler(args)
        except Exception as e:
            logger.error(f"Command '{command}' failed: {e}")
            raise
    
    def _get_handler(self, command: str, args: Dict[str, Any]) -> Optional[Callable]:
        """Get handler function for command and optional subcommand.
        
        Args:
            command: Main command name
            args: Parsed arguments dictionary (may contain subcommand keys)
            
        Returns:
            Handler function or None if command is unknown
        """
        simple_handlers = {
            'inbox': self._handle_inbox,
            'sent': self._handle_sent,
            'drafts': self._handle_drafts,
            'trash': self._handle_trash,
            'search': self._handle_search,
            'compose': self._handle_compose,
            'refresh': self._handle_refresh,
        }
        
        if command in simple_handlers:
            return simple_handlers[command]
        
        # Commands with subcommands
        if command == 'email':
            return self._get_email_handler(args)
        elif command == 'attachments':
            return self._get_attachments_handler(args)
        elif command == 'database':
            return self._get_database_handler(args)
        elif command == 'config':
            return self._get_config_handler(args)
        
        return None
    
    def _get_email_handler(self, args: Dict[str, Any]) -> Optional[Callable]:
        """Get handler for email subcommand."""
        email_command = args.get('email_command')
        email_handlers = {
            'view': self._handle_email_view,
            'delete': self._handle_email_delete,
            'flag': self._handle_email_flag,
            'unflag': self._handle_email_unflag,
            'move': self._handle_email_move,
        }
        return email_handlers.get(email_command)
    
    def _get_attachments_handler(self, args: Dict[str, Any]) -> Optional[Callable]:
        """Get handler for attachments subcommand."""
        attachment_command = args.get('attachment_command')
        attachment_handlers = {
            'list': self._handle_attachments_list,
            'download': self._handle_attachments_download,
            'downloads': self._handle_attachments_downloads,
            'open': self._handle_attachments_open,
        }
        return attachment_handlers.get(attachment_command)
    
    def _get_database_handler(self, args: Dict[str, Any]) -> Optional[Callable]:
        """Get handler for database subcommand."""
        db_command = args.get('db_command')
        db_handlers = {
            'backup': self._handle_database_backup,
            'export': self._handle_database_export,
            'delete': self._handle_database_delete,
            'info': self._handle_database_info,
        }
        return db_handlers.get(db_command)
    
    def _get_config_handler(self, args: Dict[str, Any]) -> Optional[Callable]:
        """Get handler for config subcommand."""
        config_command = args.get('config_command')
        config_handlers = {
            'list': self._handle_config_list,
            'get': self._handle_config_get,
            'set': self._handle_config_set,
            'reset': self._handle_config_reset,
        }
        return config_handlers.get(config_command)
    
    def get_available_commands(self) -> Dict[str, str]:
        """Get all available commands and their descriptions.
        
        Returns:
            Dictionary mapping command names to descriptions
        """
        return {
            # Folder viewing commands
            'inbox': 'View emails in the inbox',
            'sent': 'View sent emails',
            'drafts': 'View draft emails',
            'trash': 'View deleted emails',
            # Email operations
            'email': 'Email operations (view, delete, flag, etc)',
            # Search
            'search': 'Search emails by keyword',
            # Compose
            'compose': 'Compose a new email',
            # Attachments
            'attachments': 'Attachment operations',
            # Sync
            'refresh': 'Fetch new emails from server',
            # Database
            'database': 'Database operations (backup, export, etc)',
            # Config
            'config': 'Configuration management',
        }
    

    # Command Handlers
    

    # Folder viewing commands
    
    async def _handle_inbox(self, args: Dict[str, Any]) -> bool:
        """Route to inbox view."""
        return await self._handle_folder('inbox', args)
    
    async def _handle_sent(self, args: Dict[str, Any]) -> bool:
        """Route to sent view."""
        return await self._handle_folder('sent', args)
    
    async def _handle_drafts(self, args: Dict[str, Any]) -> bool:
        """Route to drafts view."""
        return await self._handle_folder('drafts', args)
    
    async def _handle_trash(self, args: Dict[str, Any]) -> bool:
        """Route to trash view."""
        return await self._handle_folder('trash', args)
    
    async def _handle_folder(self, folder: str, args: Dict[str, Any]) -> bool:
        """Generic folder view handler."""
        limit = args.get('limit', 10)
        filters = self._build_filters(args)
        
        return await view_folder(
            folder=folder,
            limit=limit,
            filters=filters,
            console=self.console
        )
    

    # Search command
    
    async def _handle_search(self, args: Dict[str, Any]) -> bool:
        """Route to search feature."""
        keyword = args.get('keyword')
        folder = args.get('folder', 'inbox')
        limit = args.get('limit', 50)
        search_all = args.get('all', False)
        
        if not keyword:
            raise ValueError("Search keyword is required")
        
        return await search_emails(
            keyword=keyword,
            folder=folder,
            limit=limit,
            search_all=search_all,
            console=self.console
        )
    

    # Compose command
    
    async def _handle_compose(self, args: Dict[str, Any]) -> bool:
        """Route to compose feature."""
        return await compose_email(console=self.console)
    

    # Refresh/Sync command
    
    async def _handle_refresh(self, args: Dict[str, Any]) -> bool:
        """Route to sync feature."""
        full = args.get('all', False)
        return await sync_emails(full=full, console=self.console)
    

    # Email subcommands
    
    async def _handle_email_view(self, args: Dict[str, Any]) -> bool:
        """Route to view single email."""
        email_id = args.get('id')
        folder = args.get('folder', 'inbox')
        
        if not email_id:
            raise ValueError("Email ID is required")
        
        return await view_email(email_id, folder, console=self.console)
    
    async def _handle_email_delete(self, args: Dict[str, Any]) -> bool:
        """Route to delete operation."""
        email_id = args.get('id')
        folder = args.get('folder', 'inbox')
        permanent = args.get('permanent', False)
        
        if not email_id:
            raise ValueError("Email ID is required")
        
        return await delete_email(
            email_id=email_id,
            folder=folder,
            permanent=permanent,
            console=self.console
        )
    
    async def _handle_email_move(self, args: Dict[str, Any]) -> bool:
        """Route to move operation."""
        email_id = args.get('id')
        from_folder = args.get('source', 'inbox')
        to_folder = args.get('destination')
        
        if not email_id or not to_folder:
            raise ValueError("Email ID and destination folder are required")
        
        return await move_email(
            email_id=email_id,
            from_folder=from_folder,
            to_folder=to_folder,
            console=self.console
        )
    
    async def _handle_email_flag(self, args: Dict[str, Any]) -> bool:
        """Route to flag operation."""
        email_id = args.get('id')
        folder = args.get('folder', 'inbox')
        
        if not email_id:
            raise ValueError("Email ID is required")
        
        return await flag_email(
            email_id=email_id,
            folder=folder,
            console=self.console
        )
    
    async def _handle_email_unflag(self, args: Dict[str, Any]) -> bool:
        """Route to unflag operation."""
        email_id = args.get('id')
        folder = args.get('folder', 'inbox')
        
        if not email_id:
            raise ValueError("Email ID is required")
        
        return await unflag_email(
            email_id=email_id,
            folder=folder,
            console=self.console
        )
    

    # Attachments subcommands
    
    async def _handle_attachments_list(self, args: Dict[str, Any]) -> bool:
        """Route to list attachments."""
        email_id = args.get('id')
        folder = args.get('folder', 'inbox')
        
        if not email_id:
            raise ValueError("Email ID is required")
        
        return await list_attachments(email_id, folder, console=self.console)
    
    async def _handle_attachments_download(self, args: Dict[str, Any]) -> bool:
        """Route to download attachments."""
        email_id = args.get('id')
        folder = args.get('folder', 'inbox')
        index = args.get('index')
        download_all = args.get('all', False)
        
        if not email_id:
            raise ValueError("Email ID is required")
        
        if download_all or index is None:
            return await download_all_attachments(
                email_id, folder, console=self.console
            )
        else:
            return await download_attachment(
                email_id, index, folder, console=self.console
            )
    
    async def _handle_attachments_downloads(self, args: Dict[str, Any]) -> bool:
        """Route to list downloaded attachments."""
        return await list_downloads(console=self.console)
    
    async def _handle_attachments_open(self, args: Dict[str, Any]) -> bool:
        """Route to open attachment."""
        filename = args.get('filename')
        
        if not filename:
            raise ValueError("Filename is required")
        
        return await open_attachment(filename, console=self.console)
    

    # Database subcommands
    
    async def _handle_database_backup(self, args: Dict[str, Any]) -> bool:
        """Route to backup operation."""
        from pathlib import Path
        path = args.get('path')
        backup_path = Path(path) if path else None
        
        return await backup_database(path=backup_path, console=self.console)
    
    async def _handle_database_export(self, args: Dict[str, Any]) -> bool:
        """Route to export operation."""
        from pathlib import Path
        folder = args.get('folder')
        path = args.get('path', './exports')
        export_path = Path(path)
        
        return await export_emails(
            folder=folder,
            path=export_path,
            console=self.console
        )
    
    async def _handle_database_delete(self, args: Dict[str, Any]) -> bool:
        """Route to delete database operation."""
        confirm = args.get('confirm', False)
        return await delete_database(confirm=confirm, console=self.console)
    
    async def _handle_database_info(self, args: Dict[str, Any]) -> bool:
        """Route to get database info.
        
        Note: This is a placeholder. Implement actual database info retrieval
        in the maintenance module if needed.
        """
        # TODO: Implement database info retrieval
        logger.info("Database info command not yet implemented")
        return True
    

    # Config subcommands
    
    async def _handle_config_list(self, args: Dict[str, Any]) -> bool:
        """Route to list config."""
        # TODO: Implement config list
        logger.info("Config list command not yet implemented")
        return True
    
    async def _handle_config_get(self, args: Dict[str, Any]) -> bool:
        """Route to get config value."""
        key = args.get('key')
        if not key:
            raise ValueError("Config key is required")
        # TODO: Implement config get
        logger.info(f"Config get command not yet implemented for key: {key}")
        return True
    
    async def _handle_config_set(self, args: Dict[str, Any]) -> bool:
        """Route to set config value."""
        key = args.get('key')
        value = args.get('value')
        if not key or not value:
            raise ValueError("Config key and value are required")
        # TODO: Implement config set
        logger.info(f"Config set command not yet implemented for {key}={value}")
        return True
    
    async def _handle_config_reset(self, args: Dict[str, Any]) -> bool:
        """Route to reset config."""
        key = args.get('key')
        # TODO: Implement config reset
        if key:
            logger.info(f"Config reset command not yet implemented for key: {key}")
        else:
            logger.info("Config reset command not yet implemented for all keys")
        return True
    

    # Helper Methods
    
    @staticmethod
    def _build_filters(args: Dict[str, Any]) -> Optional[EmailFilters]:
        """Build EmailFilters from arguments."""
        flagged = None
        if args.get('flagged'):
            flagged = True
        elif args.get('unflagged'):
            flagged = False
        
        unread = None
        if args.get('unread'):
            unread = True
        elif args.get('read'):
            unread = False
        
        filters = EmailFilters(
            flagged=flagged,
            unread=unread,
            has_attachments=args.get('has_attachments', False),
            from_address=args.get('from_address'),
            subject_contains=args.get('subject')
        )
        
        return filters if filters.has_filters() else None