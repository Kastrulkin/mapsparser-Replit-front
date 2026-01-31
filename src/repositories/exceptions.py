"""
Custom exceptions for repositories
"""


class RepositoryError(Exception):
    """Base exception for repository errors"""
    pass


class DuplicateRecordError(RepositoryError):
    """Raised when trying to insert a duplicate record (unique constraint violation)"""
    pass


class OrphanRecordError(RepositoryError):
    """Raised when trying to insert/update with invalid foreign key reference"""
    pass


class RecordNotFoundError(RepositoryError):
    """Raised when a record is not found"""
    pass
