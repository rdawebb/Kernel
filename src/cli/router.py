"""Routes CLI commands to feature modules."""

from typing import Any, Dict, Optional

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
    async def route(self, command: str, args: Dict[str, Any]) -> bool:
        """Route command to feature.
        
        Args:
            command: Command name
            args: Parsed arguments dictionary
            
        Returns:
            True if command executed successfully
            
        Raises:
            ValueError: If command is unknown
        """
        handler = self._get_handler(command)
        if not handler:
            raise ValueError(f"Unknown command: {command}")
        
        try:
            return await handler(args)
        except Exception as e:
            logger.error(f"Command '{command}' failed: {e}")
            raise
    
    def _get_handler(self, command: str):
        """Get handler function for command."""
        handlers = {
            # Compose
            'compose': self._handle_compose,
            
            # View
            'view': self._handle_view,
            'inbox': self._handle_inbox,
            'sent': self._handle_sent,
            'drafts': self._handle_drafts,
            'trash': self._handle_trash,
            
            # Search
            'search': self._handle_search,
            
            # Manage
            'delete': self._handle_delete,
            'move': self._handle_move,
            'flag': self._handle_flag,
            'unflag': self._handle_unflag,
            
            # Attachments
            'attachments': self._handle_attachments,
            
            # Sync
            'sync': self._handle_sync,
            'refresh': self._handle_sync,  # Alias
            
            # Maintenance
            'backup': self._handle_backup,
            'export': self._handle_export,
            'delete-db': self._handle_delete_db,
        }
        
        return handlers.get(command)
    

    # Command Handlers
    
    async def _handle_compose(self, args: Dict[str, Any]) -> bool:
        """Route to compose feature."""
        return await compose_email(console=self.console)
    
    async def _handle_view(self, args: Dict[str, Any]) -> bool:
        """Route to view single email."""
        email_id = args.get('id')
        folder = args.get('folder', 'inbox')
        
        if not email_id:
            raise ValueError("Email ID is required")
        
        return await view_email(email_id, folder, console=self.console)
    
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
        limit = args.get('limit', 50)
        filters = self._build_filters(args)
        
        return await view_folder(
            folder=folder,
            limit=limit,
            filters=filters,
            console=self.console
        )
    
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
    
    async def _handle_delete(self, args: Dict[str, Any]) -> bool:
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
    
    async def _handle_move(self, args: Dict[str, Any]) -> bool:
        """Route to move operation."""
        email_id = args.get('id')
        from_folder = args.get('from', 'inbox')
        to_folder = args.get('to')
        
        if not email_id or not to_folder:
            raise ValueError("Email ID and destination folder are required")
        
        return await move_email(
            email_id=email_id,
            from_folder=from_folder,
            to_folder=to_folder,
            console=self.console
        )
    
    async def _handle_flag(self, args: Dict[str, Any]) -> bool:
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
    
    async def _handle_unflag(self, args: Dict[str, Any]) -> bool:
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
    
    async def _handle_attachments(self, args: Dict[str, Any]) -> bool:
        """Route to attachments operations."""
        subcommand = args.get('attachment_command', 'list')
        email_id = args.get('id')
        folder = args.get('folder', 'inbox')
        
        if subcommand == 'list':
            if not email_id:
                raise ValueError("Email ID is required")
            return await list_attachments(email_id, folder, console=self.console)
        elif subcommand == 'download':
            if not email_id:
                raise ValueError("Email ID is required")
            
            index = args.get('index')
            if index is not None:
                return await download_attachment(
                    email_id, index, folder, console=self.console
                )
            else:
                return await download_all_attachments(
                    email_id, folder, console=self.console
                )
        elif subcommand == 'downloads':
            return await list_downloads(console=self.console)  
        elif subcommand == 'open':
            filename = args.get('filename')
            if not filename:
                raise ValueError("Filename is required")
            return await open_attachment(filename, console=self.console)
        else:
            raise ValueError(f"Unknown attachments subcommand: {subcommand}")
    
    async def _handle_sync(self, args: Dict[str, Any]) -> bool:
        """Route to sync feature."""
        full = args.get('all', False)
        return await sync_emails(full=full, console=self.console)
    
    async def _handle_backup(self, args: Dict[str, Any]) -> bool:
        """Route to backup operation."""
        from pathlib import Path
        path = args.get('path')
        backup_path = Path(path) if path else None
        
        return await backup_database(path=backup_path, console=self.console)
    
    async def _handle_export(self, args: Dict[str, Any]) -> bool:
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
    
    async def _handle_delete_db(self, args: Dict[str, Any]) -> bool:
        """Route to delete database operation."""
        confirm = args.get('confirm', False)
        return await delete_database(confirm=confirm, console=self.console)
    

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