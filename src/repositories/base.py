"""
Base repository class with SQL logging and error handling
"""
import logging
from typing import Any, Optional
from psycopg2 import IntegrityError
from psycopg2.errorcodes import UNIQUE_VIOLATION, FOREIGN_KEY_VIOLATION

logger = logging.getLogger('repositories')


class BaseRepository:
    """
    Base class for all repositories.
    
    Features:
    - SQL query logging (debug level)
    - Error handling with typed exceptions
    - No commit() - transactions managed at route handler level
    """
    
    def __init__(self, connection):
        """
        Initialize repository with database connection.
        
        Args:
            connection: Database connection (from Flask g.db or DatabaseManager)
        """
        self.conn = connection
        self._logger = logger
    
    def _execute(self, cursor, query: str, params: tuple = ()) -> Any:
        """
        Execute query with logging and error handling.
        
        Args:
            cursor: Database cursor
            query: SQL query
            params: Query parameters
            
        Returns:
            Result of cursor.execute()
            
        Raises:
            DuplicateRecordError: On unique violation
            OrphanRecordError: On foreign key violation
        """
        # Log SQL query at debug level
        self._logger.debug(f"SQL: {query[:200]}... | Params: {params[:5] if len(params) > 5 else params}")
        
        try:
            return cursor.execute(query, params)
        except IntegrityError as e:
            # Convert PostgreSQL error codes to typed exceptions
            # Import here to avoid circular dependencies
            try:
                from repositories.exceptions import DuplicateRecordError, OrphanRecordError
            except ImportError:
                # Fallback if exceptions module not available
                class DuplicateRecordError(Exception):
                    pass
                class OrphanRecordError(Exception):
                    pass
            
            if e.pgcode == UNIQUE_VIOLATION:  # '23505'
                raise DuplicateRecordError(f"Duplicate record: {str(e)}")
            elif e.pgcode == FOREIGN_KEY_VIOLATION:  # '23503'
                raise OrphanRecordError(f"Foreign key violation: {str(e)}")
            # Re-raise other IntegrityErrors
            raise
    
    def _get_cursor(self):
        """Get cursor from connection"""
        return self.conn.cursor()
