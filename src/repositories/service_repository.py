"""
Service Repository - Phase 3.5 compliant
- Explicit column lists (no SELECT *)
- No commit() in repository
- Uses connection directly (not DatabaseManager)
"""
from typing import List, Dict, Any, Optional
from repositories.base import BaseRepository

# Explicit column list for UserServices (excluding legacy chatgpt_context)
SERVICE_COLUMNS = [
    'id', 'user_id', 'business_id', 'category', 'name', 'description',
    'keywords', 'price', 'optimized_name', 'optimized_description',
    'is_active', 'created_at', 'updated_at'
]

SERVICE_COLUMNS_STR = ', '.join(SERVICE_COLUMNS)


class ServiceRepository(BaseRepository):
    """
    Repository for UserServices table.
    
    Phase 3.5 compliance:
    - Explicit column lists (no SELECT *)
    - No commit() - transactions managed at route handler level
    - Uses connection directly (from g.db)
    - Excludes legacy column: chatgpt_context
    """
    
    def __init__(self, connection):
        """
        Initialize repository with database connection.
        
        Args:
            connection: Database connection (from Flask g.db or DatabaseManager.conn)
        """
        super().__init__(connection)
    
    def get_by_id(self, service_id: str) -> Optional[Dict[str, Any]]:
        """
        Get service by ID.
        
        Args:
            service_id: Service ID
            
        Returns:
            Service dict or None if not found
        """
        cursor = self._get_cursor()
        query = f"SELECT {SERVICE_COLUMNS_STR} FROM UserServices WHERE id = ?"
        self._execute(cursor, query, (service_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Convert row to dict
        if hasattr(row, 'keys'):
            return dict(row)
        else:
            return dict(zip(SERVICE_COLUMNS, row))
    
    def get_by_business_id(self, business_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Get services by business ID.
        
        Args:
            business_id: Business ID
            active_only: If True, only return active services
            
        Returns:
            List of service dicts
        """
        cursor = self._get_cursor()
        if active_only:
            query = f"""
                SELECT {SERVICE_COLUMNS_STR}
                FROM UserServices 
                WHERE business_id = ? AND is_active = 1
                ORDER BY created_at DESC
            """
        else:
            query = f"""
                SELECT {SERVICE_COLUMNS_STR}
                FROM UserServices 
                WHERE business_id = ?
                ORDER BY created_at DESC
            """
        
        self._execute(cursor, query, (business_id,))
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            if hasattr(row, 'keys'):
                result.append(dict(row))
            else:
                result.append(dict(zip(SERVICE_COLUMNS, row)))
        
        return result
    
    def create(self, service_data: Dict[str, Any]) -> str:
        """
        Create a new service.
        
        Note: No commit() - must be called at route handler level.
        
        Args:
            service_data: Service data dict with required fields:
                - id: Service ID
                - name: Service name (required)
                - business_id: Business ID (optional, but recommended)
                - category, description, keywords, price: Optional
                - optimized_name, optimized_description: Optional
                
        Returns:
            Service ID
        """
        cursor = self._get_cursor()
        
        # Build query dynamically based on provided fields
        fields = ['id', 'name']  # Required
        values = [
            service_data['id'],
            service_data['name']
        ]
        
        # Add business_id if provided
        if 'business_id' in service_data:
            fields.insert(1, 'business_id')  # Insert after 'id'
            values.insert(1, service_data['business_id'])
        
        # Optional fields
        optional_fields = ['user_id', 'category', 'description', 'keywords', 'price',
                          'optimized_name', 'optimized_description', 'is_active']
        for field in optional_fields:
            if field in service_data:
                fields.append(field)
                values.append(service_data[field])
        
        # Add created_at with CURRENT_TIMESTAMP (SQL expression, not parameter)
        fields.append('created_at')
        
        fields_str = ', '.join(fields)
        # Use ? for all values, then CURRENT_TIMESTAMP for created_at
        placeholders = ', '.join(['?' for _ in values] + ['CURRENT_TIMESTAMP'])
        
        query = f"INSERT INTO UserServices ({fields_str}) VALUES ({placeholders})"
        self._execute(cursor, query, tuple(values))
        
        # NO COMMIT - managed at route handler level
        return service_data['id']
    
    def update(self, service_id: str, service_data: Dict[str, Any]) -> bool:
        """
        Update an existing service.
        
        Note: No commit() - must be called at route handler level.
        
        Args:
            service_id: Service ID
            service_data: Fields to update (only provided fields will be updated)
            
        Returns:
            True if service was updated, False if not found
        """
        cursor = self._get_cursor()
        
        # Build update query dynamically
        allowed_fields = ['category', 'name', 'description', 'keywords', 'price',
                         'optimized_name', 'optimized_description', 'is_active']
        
        updates = []
        values = []
        
        for field in allowed_fields:
            if field in service_data:
                updates.append(f"{field} = ?")
                values.append(service_data[field])
        
        if not updates:
            return False  # Nothing to update
        
        updates.append("updated_at = CURRENT_TIMESTAMP")
        values.append(service_id)
        
        query = f"UPDATE UserServices SET {', '.join(updates)} WHERE id = ?"
        self._execute(cursor, query, tuple(values))
        
        # NO COMMIT - managed at route handler level
        return cursor.rowcount > 0
    
    def delete(self, service_id: str) -> bool:
        """
        Delete (soft delete) a service by setting is_active = 0.
        
        Note: No commit() - must be called at route handler level.
        
        Args:
            service_id: Service ID
            
        Returns:
            True if service was deleted, False if not found
        """
        cursor = self._get_cursor()
        query = "UPDATE UserServices SET is_active = 0, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
        self._execute(cursor, query, (service_id,))
        
        # NO COMMIT - managed at route handler level
        return cursor.rowcount > 0
