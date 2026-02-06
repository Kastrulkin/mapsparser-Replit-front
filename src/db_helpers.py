"""
Database connection helpers for Flask routes
"""
from flask import g
from database_manager import DatabaseManager


def get_db():
    """
    Get database connection from Flask g (global context).
    Creates connection if it doesn't exist.
    
    Usage in routes:
        from db_helpers import get_db
        db = get_db()
        # For repositories, use db.conn directly:
        repo = BusinessRepository(db.conn)
        # Or use cursor:
        cursor = db.conn.cursor()
        ...
        db.conn.commit()  # Commit at route handler level
    """
    if 'db' not in g:
        # Use DatabaseManager for compatibility with existing code
        g.db = DatabaseManager()
    
    return g.db


def close_db(e=None):
    """
    Close database connection.
    Should be registered with app.teardown_appcontext()
    """
    db = g.pop('db', None)
    if db is not None:
        db.close()
