"""
Review Repository - Phase 3.5 compliant
- Explicit column lists (no SELECT *)
- No commit() in repository
- Uses connection directly (not DatabaseManager)
"""
from typing import List, Dict, Any, Optional
from datetime import datetime
from repositories.base import BaseRepository

# Explicit column list for ExternalBusinessReviews (all columns are needed, no legacy)
REVIEW_COLUMNS = [
    'id', 'business_id', 'account_id', 'source', 'external_review_id',
    'rating', 'author_name', 'author_profile_url', 'text', 'published_at',
    'response_text', 'response_at', 'lang', 'raw_payload',
    'data_source', 'quality_score', 'raw_snapshot',
    'created_at', 'updated_at'
]

REVIEW_COLUMNS_STR = ', '.join(REVIEW_COLUMNS)


class ReviewRepository(BaseRepository):
    """
    Repository for ExternalBusinessReviews table.
    
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
        self._logger = logging.getLogger(__name__)
    
    def get_by_id(self, review_id: str) -> Optional[Dict[str, Any]]:
        """
        Get review by ID.
        
        Args:
            review_id: Review ID
            
        Returns:
            Review dict or None if not found
        """
        cursor = self._get_cursor()
        query = f"SELECT {REVIEW_COLUMNS_STR} FROM ExternalBusinessReviews WHERE id = ?"
        self._execute(cursor, query, (review_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        # Convert row to dict
        if hasattr(row, 'keys'):
            return dict(row)
        else:
            return dict(zip(REVIEW_COLUMNS, row))
    
    def get_by_business_id(
        self, 
        business_id: str, 
        source: Optional[str] = None,
        with_response_only: Optional[bool] = None,
        limit: Optional[int] = None,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get reviews by business ID.
        
        Args:
            business_id: Business ID
            source: Optional source filter (e.g., 'yandex', 'google')
            with_response_only: If True, only reviews with responses
            limit: Optional limit on number of results
            offset: Offset for pagination
            
        Returns:
            List of review dicts, ordered by published_at DESC (newest first)
        """
        cursor = self._get_cursor()
        
        # Build WHERE clause
        conditions = ["business_id = ?"]
        params = [business_id]
        
        if source:
            conditions.append("source = ?")
            params.append(source)
        
        if with_response_only is True:
            conditions.append("response_text IS NOT NULL")
        elif with_response_only is False:
            conditions.append("response_text IS NULL")
        
        where_clause = " AND ".join(conditions)
        
        # Build query
        query = f"""
            SELECT {REVIEW_COLUMNS_STR}
            FROM ExternalBusinessReviews 
            WHERE {where_clause}
            ORDER BY 
                COALESCE(published_at, created_at) DESC,
                created_at DESC
        """
        
        if limit:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        
        self._execute(cursor, query, tuple(params))
        rows = cursor.fetchall()
        
        result = []
        for row in rows:
            if hasattr(row, 'keys'):
                result.append(dict(row))
            else:
                result.append(dict(zip(REVIEW_COLUMNS, row)))
        
        return result
    
    def get_statistics(self, business_id: str, source: Optional[str] = None) -> Dict[str, Any]:
        """
        Get review statistics for a business.
        
        Args:
            business_id: Business ID
            source: Optional source filter
            
        Returns:
            Dict with statistics:
                - total: Total number of reviews
                - with_response: Number of reviews with responses
                - without_response: Number of reviews without responses
                - average_rating: Average rating (if available)
        """
        cursor = self._get_cursor()
        
        conditions = ["business_id = ?"]
        params = [business_id]
        
        if source:
            conditions.append("source = ?")
            params.append(source)
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
            SELECT 
                COUNT(*) as total,
                COUNT(CASE WHEN response_text IS NOT NULL THEN 1 END) as with_response,
                COUNT(CASE WHEN response_text IS NULL THEN 1 END) as without_response,
                AVG(rating) as average_rating
            FROM ExternalBusinessReviews 
            WHERE {where_clause}
        """
        
        self._execute(cursor, query, tuple(params))
        row = cursor.fetchone()
        
        if not row:
            return {
                'total': 0,
                'with_response': 0,
                'without_response': 0,
                'average_rating': None
            }
        
        if hasattr(row, 'keys'):
            stats = dict(row)
        else:
            columns = ['total', 'with_response', 'without_response', 'average_rating']
            stats = dict(zip(columns, row))
        
        # Convert average_rating to float if not None
        if stats.get('average_rating') is not None:
            stats['average_rating'] = float(stats['average_rating'])
        
        return stats
    
    def get_by_external_id(
        self, 
        external_review_id: Optional[str], 
        business_id: str, 
        source: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get review by external_review_id, business_id, and source.
        
        Args:
            external_review_id: External review ID
            business_id: Business ID
            source: Source name
            
        Returns:
            Review dict or None if not found
        """
        if not external_review_id:
            return None
        
        cursor = self._get_cursor()
        query = f"""
            SELECT {REVIEW_COLUMNS_STR}
            FROM ExternalBusinessReviews 
            WHERE external_review_id = ? AND business_id = ? AND source = ?
            LIMIT 1
        """
        self._execute(cursor, query, (external_review_id, business_id, source))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        if hasattr(row, 'keys'):
            return dict(row)
        else:
            return dict(zip(REVIEW_COLUMNS, row))
    
    def upsert(
        self, 
        review_data: Dict[str, Any],
        source: str = 'api',
        quality_score: int = 100,
        raw_snapshot: Optional[Dict] = None
    ) -> str:
        """
        Upsert a review with quality score protection.
        
        Правила обновления:
        1. Обновляем если новый quality_score выше существующего
        2. Обновляем если тот же источник и данные свежее (updated_at новее на 1+ час)
        3. Не обновляем если существующий quality_score выше нового
        
        Note: No commit() - must be called at route handler level.
        
        Args:
            review_data: Review data dict with required fields:
                - id: Review ID
                - business_id: Business ID (required)
                - source: Source name (required)
                - Other fields optional
            source: Data source ('api', 'html', 'meta', etc.)
            quality_score: Quality score (0-100)
            raw_snapshot: Raw data snapshot (only stored if quality_score < 50)
                
        Returns:
            Review ID
        """
        import json
        from datetime import datetime, timedelta
        
        cursor = self._get_cursor()
        
        # Required fields
        required_fields = ['id', 'business_id', 'source']
        for field in required_fields:
            if field not in review_data:
                raise ValueError(f"Required field missing: {field}")
        
        # Проверяем существующую запись
        existing = self.get_by_external_id(
            review_data.get('external_review_id'),
            review_data['business_id'],
            review_data['source']
        )
        
        if existing:
            existing_score = existing.get('quality_score', 0) or 0
            existing_source = existing.get('data_source', 'unknown')
            existing_updated = existing.get('updated_at')
            
            # Правило 1: Новый quality_score выше - обновляем
            if quality_score > existing_score:
                # Обновляем - продолжаем
                pass
            # Правило 2: Тот же источник и данные свежее - обновляем
            elif source == existing_source and existing_updated:
                # Проверяем, что новые данные свежее (в пределах 1 часа)
                try:
                    if isinstance(existing_updated, str):
                        # Парсим строку с учетом timezone
                        existing_dt = datetime.fromisoformat(existing_updated.replace('Z', '+00:00'))
                    else:
                        existing_dt = existing_updated
                    
                    # PostgreSQL возвращает timezone-aware datetime, SQLite - naive
                    # Приводим к naive для единообразия
                    if existing_dt.tzinfo is not None:
                        existing_dt = existing_dt.replace(tzinfo=None)
                    
                    # Если данные старше 1 часа - обновляем
                    now = datetime.now()
                    if now - existing_dt > timedelta(hours=1):
                        # Обновляем - продолжаем
                        pass
                    else:
                        # Данные свежие, не обновляем
                        self._logger.debug(
                            f"Skipping upsert: existing data is fresh (updated_at={existing_updated})"
                        )
                        return existing['id']
                except Exception as e:
                    self._logger.warning(f"Error parsing updated_at: {e}, updating anyway")
                    # Обновляем при ошибке парсинга
                    pass
            # Правило 3: Существующий quality_score выше - не трогаем
            else:
                self._logger.debug(
                    f"Skipping upsert: existing quality_score={existing_score} >= new={quality_score}"
                )
                return existing['id']
        
        # Добавляем метаданные
        review_data['data_source'] = source
        review_data['quality_score'] = quality_score
        
        # raw_snapshot только для плохих данных (экономия места)
        if quality_score < 50 and raw_snapshot:
            # Ограничиваем размер snapshot (первые 1000 символов)
            snapshot_str = json.dumps(raw_snapshot, ensure_ascii=False)
            if len(snapshot_str) > 1000:
                snapshot_str = snapshot_str[:1000] + '...'
            review_data['raw_snapshot'] = snapshot_str
        else:
            review_data['raw_snapshot'] = None
        
        # Build INSERT columns
        insert_fields = required_fields.copy()
        insert_values = [review_data[field] for field in required_fields]
        
        # Optional fields
        optional_fields = ['account_id', 'external_review_id', 'rating', 'author_name',
                          'author_profile_url', 'text', 'published_at', 'response_text',
                          'response_at', 'lang', 'raw_payload', 'data_source', 
                          'quality_score', 'raw_snapshot']
        
        for field in optional_fields:
            if field in review_data:
                insert_fields.append(field)
                insert_values.append(review_data[field])
        
        insert_fields.extend(['created_at', 'updated_at'])
        insert_values.extend(['CURRENT_TIMESTAMP', 'CURRENT_TIMESTAMP'])
        
        # Build UPDATE clause (update all fields except id, created_at)
        # Но только если quality_score выше или данные свежее
        update_fields = [f for f in insert_fields if f not in ['id', 'created_at']]
        update_clause = ', '.join([f"{f} = excluded.{f}" for f in update_fields])
        
        fields_str = ', '.join(insert_fields)
        placeholders = ', '.join(['?' for _ in insert_fields])
        
        query = f"""
            INSERT INTO ExternalBusinessReviews ({fields_str})
            VALUES ({placeholders})
            ON CONFLICT(id) DO UPDATE SET
                {update_clause}
        """
        
        self._execute(cursor, query, tuple(insert_values))
        
        # NO COMMIT - managed at route handler level
        return review_data['id']
    
    def update_response(self, review_id: str, response_text: str, response_at: Optional[datetime] = None) -> bool:
        """
        Update response to a review.
        
        Note: No commit() - must be called at route handler level.
        
        Args:
            review_id: Review ID
            response_text: Response text
            response_at: Response timestamp (defaults to now)
            
        Returns:
            True if review was updated, False if not found
        """
        cursor = self._get_cursor()
        
        if response_at is None:
            response_at = datetime.utcnow()
        
        query = """
            UPDATE ExternalBusinessReviews 
            SET response_text = ?, response_at = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        self._execute(cursor, query, (response_text, response_at, review_id))
        
        # NO COMMIT - managed at route handler level
        return cursor.rowcount > 0
