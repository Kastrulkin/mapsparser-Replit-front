"""
Business Repository - Phase 3.5 compliant
- Explicit column lists (no SELECT *)
- No commit() in repository
- Uses connection directly (not DatabaseManager)
"""
from typing import List, Dict, Any, Optional
from repositories.base import BaseRepository

# Explicit column list for Businesses (excluding legacy chatgpt_* columns)
BUSINESS_COLUMNS = [
    'id', 'name', 'description', 'industry', 'business_type',
    'address', 'working_hours', 'phone', 'email', 'website',
    'owner_id', 'network_id', 'is_active',
    'subscription_tier', 'subscription_status',
    'created_at', 'updated_at',
    'city', 'country', 'timezone',
    'latitude', 'longitude', 'working_hours_json',
    'waba_phone_id', 'waba_access_token', 'whatsapp_phone', 'whatsapp_verified',
    'telegram_bot_token',
    'ai_agent_enabled', 'ai_agent_type', 'ai_agent_id', 'ai_agent_tone', 
    'ai_agent_restrictions', 'ai_agent_language',
    'yandex_org_id', 'yandex_url', 'yandex_rating', 'yandex_reviews_total', 
    'yandex_reviews_30d', 'yandex_last_sync',
    'telegram_bot_connected', 'telegram_username',
    'stripe_customer_id', 'stripe_subscription_id',
    'trial_ends_at', 'subscription_ends_at',
    'moderation_status', 'moderation_notes'
]

BUSINESS_COLUMNS_STR = ', '.join(BUSINESS_COLUMNS)


class BusinessRepository(BaseRepository):
    """
    Repository for Businesses table.
    
    Phase 3.5 compliance:
    - Explicit column lists (no SELECT *)
    - No commit() - transactions managed at route handler level
    - Uses connection directly (from g.db)
    """
    
    def __init__(self, connection):
        """
        Initialize repository with database connection.
        
        Args:
            connection: Database connection (from Flask g.db or DatabaseManager.conn)
        """
        super().__init__(connection)
    
    def get_by_id(self, business_id: str) -> Optional[Dict[str, Any]]:
        """
        Get business by ID.
        
        Args:
            business_id: Business ID
            
        Returns:
            Business dict or None if not found
        """
        cursor = self._get_cursor()
        query = f"SELECT {BUSINESS_COLUMNS_STR} FROM Businesses WHERE id = ?"
        self._execute(cursor, query, (business_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Convert row to dict
        if hasattr(row, 'keys'):
            return dict(row)
        else:
            # For tuple/list rows
            return dict(zip(BUSINESS_COLUMNS, row))
    
    def get_by_owner(self, owner_id: str) -> List[Dict[str, Any]]:
        """
        Get businesses by owner ID.
        
        Args:
            owner_id: Owner user ID
            
        Returns:
            List of business dicts
        """
        cursor = self._get_cursor()
        query = f"""
            SELECT {BUSINESS_COLUMNS_STR}
            FROM Businesses 
            WHERE owner_id = ? AND is_active = 1
            ORDER BY created_at DESC
        """
        self._execute(cursor, query, (owner_id,))
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            if hasattr(row, 'keys'):
                result.append(dict(row))
            else:
                result.append(dict(zip(BUSINESS_COLUMNS, row)))
        
        return result
    
    def get_source_by_business_id(self, business_id: str, source: str = 'yandex') -> Optional[Dict[str, Any]]:
        """
        Get business external source info.
        
        Args:
            business_id: Business ID
            source: Source name (default: 'yandex')
            
        Returns:
            Source dict or None if not found
        """
        cursor = self._get_cursor()
        query = """
            SELECT business_id, source, external_id, url, created_at, updated_at
            FROM business_sources 
            WHERE business_id = ? AND source = ?
        """
        self._execute(cursor, query, (business_id, source))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        if hasattr(row, 'keys'):
            return dict(row)
        else:
            columns = ['business_id', 'source', 'external_id', 'url', 'created_at', 'updated_at']
            return dict(zip(columns, row))
    
    def upsert_source(self, business_id: str, source: str, external_id: str, url: str) -> None:
        """
        Upsert business source (Entity Resolution).
        
        Note: No commit() - must be called at route handler level.
        
        Args:
            business_id: Business ID
            source: Source name
            external_id: External source ID
            url: Source URL
        """
        cursor = self._get_cursor()
        query = """
            INSERT INTO business_sources (business_id, source, external_id, url)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (business_id, source) 
            DO UPDATE SET 
                external_id = excluded.external_id,
                url = excluded.url,
                updated_at = CURRENT_TIMESTAMP
        """
        self._execute(cursor, query, (business_id, source, external_id, url))
        # NO COMMIT - managed at route handler level
    
    def update_yandex_fields(self, business_id: str, yandex_org_id: str, yandex_url: str) -> None:
        """
        Legacy support: update Yandex fields in Businesses table.
        Also syncs to business_sources.
        
        Note: No commit() - must be called at route handler level.
        
        Args:
            business_id: Business ID
            yandex_org_id: Yandex organization ID
            yandex_url: Yandex URL
        """
        cursor = self._get_cursor()
        query = """
            UPDATE Businesses 
            SET yandex_org_id = ?, yandex_url = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        self._execute(cursor, query, (yandex_org_id, yandex_url, business_id))
        
        # Sync to new table
        self.upsert_source(business_id, 'yandex', yandex_org_id, yandex_url)
        # NO COMMIT - managed at route handler level