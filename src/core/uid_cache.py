"""UID cache management - handles in-memory and file-based caching of highest email UID."""

import json
from pathlib import Path
from typing import Optional
from ..utils.log_manager import get_logger

logger = get_logger(__name__)

CACHE_DIR = Path.home() / ".kernel"
CACHE_PATH = CACHE_DIR / "uid_cache.json"


class UIDCache:
    """Manages caching of highest UID with memory, file, and database fallback."""
    
    def __init__(self):
        self._cached_uid: Optional[int] = None
    
    def get(self, db_fallback_func=None) -> Optional[int]:
        """Get highest UID from memory, file, or database."""

        # Check memory cache
        if self._cached_uid is not None:
            return self._cached_uid
        
        # Check file cache
        if CACHE_PATH.exists():
            try:
                with open(CACHE_PATH, 'r') as f:
                    data = json.load(f)
                    uid = data.get('highest_uid')
                    if uid is not None:
                        self._cached_uid = uid
                        return uid
            except Exception as e:
                logger.warning(f"Failed to read UID cache: {e}")
        
        # Fallback to database
        if db_fallback_func:
            uid = db_fallback_func()
            self._cached_uid = uid
            if uid is not None:
                self.update(uid)
            return uid
        
        return None
    
    def update(self, uid: int) -> None:
        """Update UID cache in memory and file."""

        self._cached_uid = uid
        
        try:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            with open(CACHE_PATH, 'w') as f:
                json.dump({'highest_uid': uid}, f)
        except Exception as e:
            logger.warning(f"Failed to update UID cache: {e}")
    
    def invalidate(self) -> None:
        """Clear in-memory cache (file cache remains for persistence)."""
        self._cached_uid = None
