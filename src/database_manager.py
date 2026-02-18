#!/usr/bin/env python3
"""
Менеджер базы данных для управления всеми 4 таблицами
"""
import os
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Any
from psycopg2.extras import Json
import psycopg2

try:
    from parsequeue_status import STATUS_PENDING, normalize_status
except ImportError:
    STATUS_PENDING = "pending"
    def normalize_status(s): return (s or "").strip() or STATUS_PENDING

class DBConnectionWrapper:
    """Wrapper around database connection"""
    def __init__(self, conn):
        self.conn = conn
        
    def cursor(self):
        return self.conn.cursor()
        
    def commit(self):
        return self.conn.commit()
        
    def rollback(self):
        return self.conn.rollback()
        
    def close(self):
        return self.conn.close()
        
    def __getattr__(self, name):
        return getattr(self.conn, name)

def get_db_connection():
    """
    Получить соединение с базой данных для runtime.

    Runtime **всегда** использует PostgreSQL через pg_db_utils.
    Попытка запустить без DATABASE_URL приведёт к RuntimeError в pg_db_utils.
    """
    from pg_db_utils import get_db_connection as _get_pg_connection

    conn = _get_pg_connection()
    return DBConnectionWrapper(conn)

class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    def __init__(self):
        self.conn = get_db_connection()
        self._closed = False
    
    def close(self):
        """Закрыть соединение"""
        if self.conn and not self._closed:
            try:
                # Коммитим все незакоммиченные изменения
                self.conn.commit()
            except:
                pass
            try:
                self.conn.close()
            except:
                pass
            self._closed = True
    
    def __enter__(self):
        """Контекстный менеджер: вход"""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер: выход"""
        self.close()
        return False
    
    # ===== USERS (Пользователи) =====
    
    def get_all_users(self) -> List[Dict[str, Any]]:
        """Получить всех пользователей"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT id, email, name, phone, created_at, is_active, is_verified, is_superadmin
            FROM users 
            ORDER BY created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Получить пользователя по ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """Получить пользователя по email"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def create_user(self, email: str, password_hash: str, name: str = None, phone: str = None) -> str:
        """Создать пользователя"""
        user_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO users (id, email, password_hash, name, phone, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (user_id, email, password_hash, name, phone, datetime.now().isoformat()))
        self.conn.commit()
        return user_id
    
    # УДАЛЕНО: authenticate_user - используйте auth_system.authenticate_user вместо этого
    # Метод был удален для унификации хеширования паролей (PBKDF2 вместо SHA256)
    
    def create_session(self, user_id: str) -> str:
        """Создать сессию для пользователя"""
        session_token = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO usersessions (token, user_id, created_at, expires_at)
            VALUES (%s, %s, %s, %s)
        """, (session_token, user_id, datetime.now().isoformat(), 
              (datetime.now() + timedelta(days=30)).isoformat()))
        self.conn.commit()
        return session_token
    
    def verify_session(self, token: str) -> Optional[Dict[str, Any]]:
        """Проверить сессию и получить данные пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT u.*, s.created_at as session_created_at
            FROM users u
            JOIN usersessions s ON u.id = s.user_id
            WHERE s.token = %s AND s.expires_at > %s
        """, (token, datetime.now().isoformat()))
        
        result = cursor.fetchone()
        return dict(result) if result else None
    
    def delete_session(self, token: str) -> bool:
        """Удалить сессию"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM usersessions WHERE token = %s", (token,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def update_user(self, user_id: str, **kwargs) -> bool:
        """Обновить пользователя"""
        cursor = self.conn.cursor()
        allowed_fields = ['name', 'phone', 'telegram_id', 'is_active', 'is_verified']
        update_fields = []
        values = []
        
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                update_fields.append(f"{field} = %s")
                values.append(value)
        
        if not update_fields:
            return True
        
        values.extend([datetime.now().isoformat(), user_id])
        query = f"UPDATE users SET {', '.join(update_fields)}, updated_at = %s WHERE id = %s"
        
        cursor.execute(query, values)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_user(self, user_id: str) -> bool:
        """Удалить пользователя (каскадное удаление)"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # ===== INVITES (Приглашения) =====
    
    def get_all_invites(self) -> List[Dict[str, Any]]:
        """Получить все приглашения"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT i.*, u.email as invited_by_email, u.name as invited_by_name
            FROM invites i
            JOIN users u ON i.invited_by = u.id
            ORDER BY i.created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_invite_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Получить приглашение по токену"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM invites WHERE token = %s", (token,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def create_invite(self, email: str, invited_by: str, expires_days: int = 7) -> str:
        """Создать приглашение"""
        invite_id = str(uuid.uuid4())
        token = str(uuid.uuid4()).replace('-', '')
        expires_at = datetime.now() + timedelta(days=expires_days)
        
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO invites (id, email, invited_by, token, expires_at, created_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (invite_id, email, invited_by, token, expires_at.isoformat(), datetime.now().isoformat()))
        self.conn.commit()
        return token
    
    def update_invite_status(self, invite_id: str, status: str) -> bool:
        """Обновить статус приглашения"""
        cursor = self.conn.cursor()
        cursor.execute("UPDATE invites SET status = %s WHERE id = %s", (status, invite_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_invite(self, invite_id: str) -> bool:
        """Удалить приглашение"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM invites WHERE id = %s", (invite_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # ===== PARSEQUEUE (Очередь запросов) =====
    
    def get_all_queue_items(self) -> List[Dict[str, Any]]:
        """Получить все элементы очереди"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT q.*, u.email as user_email, u.name as user_name
            FROM parsequeue q
            JOIN users u ON q.user_id = u.id
            ORDER BY q.created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_queue_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Получить очередь пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM parsequeue 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def add_to_queue(self, url: str, user_id: str) -> str:
        """Добавить в очередь (статус при создании — pending)."""
        queue_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO parsequeue (id, url, user_id, status, created_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (queue_id, url, user_id, STATUS_PENDING, datetime.now().isoformat()))
        self.conn.commit()
        return queue_id

    def update_queue_status(self, queue_id: str, status: str) -> bool:
        """Обновить статус элемента очереди. Запись всегда в каноническом виде (done → completed)."""
        cursor = self.conn.cursor()
        canonical = normalize_status(status)
        cursor.execute("UPDATE parsequeue SET status = %s WHERE id = %s", (canonical, queue_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_queue_item(self, queue_id: str) -> bool:
        """Удалить элемент очереди"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM parsequeue WHERE id = %s", (queue_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_pending_queue_items(self) -> List[Dict[str, Any]]:
        """Получить ожидающие элементы очереди (status = pending)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM parsequeue 
            WHERE status = %s 
            ORDER BY created_at ASC
        """, (STATUS_PENDING,))
        return [dict(row) for row in cursor.fetchall()]
    
    # ===== CARDS (Готовые отчёты) =====
    
    def get_all_cards(self) -> List[Dict[str, Any]]:
        """Получить все карточки"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT c.*, u.email as user_email, u.name as user_name
            FROM cards c
            JOIN users u ON c.user_id = u.id
            ORDER BY c.created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_cards_by_user(self, user_id: str) -> List[Dict[str, Any]]:
        """Получить карточки пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM cards 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_card_by_id(self, card_id: str) -> Optional[Dict[str, Any]]:
        """Получить карточку по ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM cards WHERE id = %s", (card_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def create_card(self, user_id: str, url: str, **kwargs) -> str:
        """Создать карточку (legacy метод, используйте save_new_card_version для версионирования)"""
        card_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        
        # Подготавливаем данные
        fields = ['url', 'title', 'address', 'phone', 'site', 'rating', 'reviews_count', 
                 'categories', 'overview', 'products', 'news', 'photos', 'features_full', 
                 'competitors', 'hours', 'hours_full', 'report_path', 'seo_score', 
                 'ai_analysis', 'recommendations']
        
        values = [card_id, user_id]
        field_names = ['id', 'user_id']
        
        for field in fields:
            if field in kwargs:
                values.append(kwargs[field])
                field_names.append(field)
        
        values.append(datetime.now().isoformat())
        field_names.append('created_at')
        
        placeholders = ', '.join(['%s' for _ in values])
        field_list = ', '.join(field_names)
        
        cursor.execute(f"INSERT INTO cards ({field_list}) VALUES ({placeholders})", values)
        self.conn.commit()
        return card_id
    
    def save_new_card_version(self, business_id: str, url: str = None, **kwargs) -> str:
        """
        Сохранить новую версию карточки с версионированием.
        
        В одной транзакции:
        1. Обновляет старую актуальную карточку (is_latest = FALSE)
        2. Определяет version новой карточки (MAX(version) + 1)
        3. Вставляет новую карточку с is_latest = TRUE
        
        Инварианты (для ручной проверки в БД):
        - Не более одной записи с is_latest = TRUE на business_id:
            SELECT business_id, COUNT(*) AS cnt
            FROM cards
            WHERE is_latest = TRUE
            GROUP BY business_id
            HAVING COUNT(*) > 1;
        
        - Новая версия не должна создаваться, если все поля карточки NULL
          (проверяется на уровне caller'а, см. sync-блок в worker).
        
        Args:
            business_id: ID бизнеса (обязательно)
            url: URL карточки (опционально)
            **kwargs: Дополнительные поля карточки
        
        Returns:
            card_id: ID созданной карточки
        """
        if not business_id:
            raise ValueError("business_id обязателен для создания версионированной карточки")
        
        card_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        
        try:
            # 1. Обновляем старую актуальную карточку
            cursor.execute("""
                UPDATE cards
                SET is_latest = FALSE
                WHERE business_id = %s AND is_latest = TRUE
            """, (business_id,))
            
            # 2. Определяем version новой карточки
            cursor.execute("""
                SELECT COALESCE(MAX(version), 0) + 1 as next_version
                FROM cards
                WHERE business_id = %s
            """, (business_id,))
            row = cursor.fetchone()
            next_version = row['next_version'] if isinstance(row, dict) else row[0]
            
            # 3. Подготавливаем данные для новой карточки
            # url уже обрабатывается отдельно выше, поэтому в fields его нет
            fields = ['title', 'address', 'phone', 'site', 'rating', 'reviews_count',
                     'categories', 'overview', 'products', 'news', 'photos', 'features_full',
                     'competitors', 'hours', 'hours_full', 'report_path', 'seo_score',
                     'ai_analysis', 'recommendations']
            
            values = [card_id, business_id]
            field_names = ['id', 'business_id']
            
            if url:
                values.append(url)
                if 'url' not in field_names:
                    field_names.append('url')

            # Поля, которые в БД хранятся как JSON/JSONB и могут приходить как dict/list.
            json_like_fields = {
                'categories',
                'overview',
                'products',
                'news',
                'photos',
                'features_full',
                'competitors',
                'hours',
                'hours_full',
                'ai_analysis',
                'recommendations',
            }

            def _adapt_value(field_name: str, value: Any) -> Any:
                """
                Универсальная адаптация для JSON-полей:
                - dict / list → psycopg2.extras.Json(value)
                - остальные типы → без изменений
                """
                if field_name in json_like_fields and isinstance(value, (dict, list)):
                    return Json(value)
                return value
            
            for field in fields:
                if field in kwargs:
                    raw_val = kwargs[field]
                    values.append(_adapt_value(field, raw_val))
                    if field not in field_names:
                        field_names.append(field)
            
            # Добавляем version и is_latest
            values.extend([next_version, True])
            field_names.extend(['version', 'is_latest'])
            
            values.append(datetime.now().isoformat())
            field_names.append('created_at')
            
            placeholders = ', '.join(['%s' for _ in values])
            field_list = ', '.join(field_names)
            
            # 4. Вставляем новую карточку
            cursor.execute(f"""
                INSERT INTO cards ({field_list}) 
                VALUES ({placeholders})
            """, values)
            
            self.conn.commit()
            return card_id
        except psycopg2.IntegrityError as e:
            # Возможная гонка из-за uq_cards_latest_per_business (unique_violation 23505).
            self.conn.rollback()
            if getattr(e, "pgcode", None) != "23505":
                # Не наш случай — пробрасываем дальше.
                raise
            print(f"[CARDS] IntegrityError(unique_violation) in save_new_card_version for business_id={business_id}: {e}")
            # Перечитываем актуальную карточку и возвращаем её id, не роняя worker.
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT id
                FROM cards
                WHERE business_id = %s AND is_latest = TRUE
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (business_id,),
            )
            row = cursor.fetchone()
            if row:
                return row["id"] if isinstance(row, dict) else row[0]
            raise
        except Exception as e:
            self.conn.rollback()
            raise Exception(f"Ошибка при сохранении новой версии карточки: {e}")

    def update_business_from_card(self, business_id: str, card: Dict[str, Any]) -> None:
        """
        Обновить таблицу businesses на основе данных карточки (card_data/cards).
        Поля обновляются только если есть в card и осмысленны.
        """
        if not business_id or not isinstance(card, dict):
            return

        # Канон: храним сайт в колонке site; website не удаляем (legacy/алиас в API).
        field_map = {
            "address": "address",
            "phone": "phone",
            "site": "site",
            "rating": "rating",
            "reviews_count": "reviews_count",
            "categories": "categories",
            "hours": "hours",
            "hours_full": "hours_full",
            "description": "description",
            "industry": "industry",
            "geo": "geo",
            "external_ids": "external_ids",
        }

        json_fields = {"categories", "hours", "hours_full", "geo", "external_ids"}

        updates = []
        values: List[Any] = []

        def has_value(v: Any) -> bool:
            if v is None:
                return False
            if isinstance(v, str):
                return bool(v.strip())
            if isinstance(v, (list, dict)):
                return len(v) > 0
            return True

        for card_key, col in field_map.items():
            v = card.get(card_key)
            if not has_value(v):
                continue

            if card_key == "rating":
                try:
                    v = float(v)
                except (TypeError, ValueError):
                    continue
            if card_key == "reviews_count":
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    continue

            if card_key in json_fields:
                if isinstance(v, (dict, list)):
                    v = Json(v)

            updates.append(f"{col} = %s")
            values.append(v)

        # Всегда обновляем last_parsed_at, если есть хоть одно обновление
        if not updates:
            return

        updates.append("last_parsed_at = CURRENT_TIMESTAMP")

        values.append(business_id)

        cursor = self.conn.cursor()
        try:
            cursor.execute(
                f"UPDATE businesses SET {', '.join(updates)} WHERE id = %s",
                values,
            )
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            # Не роняем весь воркер, но логируем на stderr
            print(f"⚠️ update_business_from_card failed for {business_id}: {e}")

    def upsert_parsed_services(self, business_id: str, user_id: str, service_rows: List[Dict[str, Any]]) -> int:
        """
        Upsert распарсенных услуг в userservices.
        Для строк с external_id используется ON CONFLICT (business_id, source, external_id) DO UPDATE.
        Без external_id — обычный INSERT.
        Возвращает количество сохранённых записей.
        """
        if not service_rows:
            return 0
        cursor = self.conn.cursor()
        saved = 0
        try:
            parsed_sources = sorted({
                (row.get("source") or "yandex_maps").strip() or "yandex_maps"
                for row in service_rows
                if isinstance(row, dict) and row.get("name")
            })
            # Перед апдейтом нового снапшота выключаем старые распарсенные строки этого source.
            # Ручные услуги не затрагиваем (у них source обычно NULL/другой, raw отсутствует).
            for src in parsed_sources:
                cursor.execute(
                    """
                    UPDATE userservices
                    SET is_active = FALSE, updated_at = CURRENT_TIMESTAMP
                    WHERE business_id = %s
                      AND source = %s
                      AND raw IS NOT NULL
                    """,
                    (business_id, src),
                )

            rows_sorted = sorted(
                service_rows,
                key=lambda r: len(str((r or {}).get("description") or "").strip()),
                reverse=True,
            )
            seen_keys = set()
            for row in rows_sorted:
                if not row or not row.get("name"):
                    continue
                sid = str(uuid.uuid4())
                name = row.get("name", "").strip()
                description = (row.get("description") or "").strip() or None
                category = (row.get("category") or "Разное").strip() or "Разное"
                source = (row.get("source") or "yandex_maps").strip() or "yandex_maps"
                external_id = row.get("external_id")
                if external_id is not None:
                    external_id = str(external_id).strip() or None
                price_from = row.get("price_from")
                price_to = row.get("price_to")
                price_str = None
                if price_from is not None:
                    price_str = str(price_from)
                elif price_to is not None:
                    price_str = str(price_to)
                dedup_key = (
                    source.lower(),
                    name.lower(),
                    category.lower(),
                    str(price_from or ""),
                    str(price_to or ""),
                    str(price_str or ""),
                )
                if dedup_key in seen_keys:
                    continue
                seen_keys.add(dedup_key)
                raw = row.get("raw")
                if isinstance(raw, (dict, list)):
                    raw = Json(raw)
                duration_minutes = row.get("duration_minutes")
                if external_id:
                    cursor.execute(
                        """
                        INSERT INTO userservices (
                            id, business_id, user_id, name, description, category,
                            source, external_id, price_from, price_to, price, raw,
                            duration_minutes, is_active, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP
                        )
                        ON CONFLICT (business_id, source, external_id) WHERE (external_id IS NOT NULL)
                        DO UPDATE SET
                            name = EXCLUDED.name,
                            description = EXCLUDED.description,
                            category = EXCLUDED.category,
                            price_from = EXCLUDED.price_from,
                            price_to = EXCLUDED.price_to,
                            price = EXCLUDED.price,
                            raw = EXCLUDED.raw,
                            duration_minutes = EXCLUDED.duration_minutes,
                            updated_at = CURRENT_TIMESTAMP
                        """,
                        (
                            sid, business_id, user_id, name, description, category,
                            source, external_id, price_from, price_to, price_str, raw,
                            duration_minutes,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        INSERT INTO userservices (
                            id, business_id, user_id, name, description, category,
                            source, external_id, price_from, price_to, price, raw,
                            duration_minutes, is_active, updated_at
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, NULL, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP
                        )
                        """,
                        (
                            sid, business_id, user_id, name, description, category,
                            source, price_from, price_to, price_str, raw,
                            duration_minutes,
                        ),
                    )
                saved += 1
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            print(f"⚠️ upsert_parsed_services failed for business_id={business_id}: {e}")
        return saved

    def get_latest_card_by_business(self, business_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить последнюю версию карточки для бизнеса.
        
        Args:
            business_id: ID бизнеса
        
        Returns:
            Словарь с данными карточки или None, если карточка не найдена
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM cards
            WHERE business_id = %s AND is_latest = TRUE
            LIMIT 1
        """, (business_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        if isinstance(row, dict):
            return row
        else:
            columns = [desc[0] for desc in cursor.description]
            return dict(zip(columns, row))
    
    def get_card_history_by_business(self, business_id: str) -> List[Dict[str, Any]]:
        """
        Получить историю всех версий карточки для бизнеса.
        
        Args:
            business_id: ID бизнеса
        
        Returns:
            Список словарей с данными карточек, отсортированный по version DESC
        """
        cursor = self.conn.cursor()
        
        # Проверяем, есть ли колонка version
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'cards' AND column_name = 'version'
        """)
        has_version = cursor.fetchone() is not None
        
        if has_version:
            cursor.execute("""
                SELECT * FROM cards
                WHERE business_id = %s
                ORDER BY version DESC
            """, (business_id,))
        else:
            # Fallback для таблиц без версионирования
            cursor.execute("""
                SELECT * FROM cards
                WHERE business_id = %s
                ORDER BY created_at DESC
            """, (business_id,))
        
        rows = cursor.fetchall()
        if not rows:
            return []
        
        columns = [desc[0] for desc in cursor.description]
        result = []
        for row in rows:
            if isinstance(row, dict):
                result.append(row)
            else:
                result.append(dict(zip(columns, row)))
        
        return result
    
    def update_card(self, card_id: str, **kwargs) -> bool:
        """Обновить карточку"""
        cursor = self.conn.cursor()
        allowed_fields = ['title', 'address', 'phone', 'site', 'rating', 'reviews_count',
                         'categories', 'overview', 'products', 'news', 'photos', 
                         'features_full', 'competitors', 'hours', 'hours_full', 
                         'report_path', 'seo_score', 'ai_analysis', 'recommendations']
        
        update_fields = []
        values = []
        
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                update_fields.append(f"{field} = %s")
                values.append(value)
        
        if not update_fields:
            return True
        
        values.append(card_id)
        query = f"UPDATE cards SET {', '.join(update_fields)} WHERE id = %s"
        
        cursor.execute(query, values)
        self.conn.commit()
        return cursor.rowcount > 0
    
    def delete_card(self, card_id: str) -> bool:
        """Удалить карточку"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM cards WHERE id = %s", (card_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    # ===== СТАТИСТИКА =====
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику системы"""
        cursor = self.conn.cursor()
        
        stats = {}
        
        # Количество пользователей
        cursor.execute("SELECT COUNT(*) as count FROM users")
        stats['users_count'] = cursor.fetchone()['count']
        
        # Количество активных пользователей
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_active = TRUE")
        stats['active_users_count'] = cursor.fetchone()['count']
        
        # Количество приглашений
        cursor.execute("SELECT COUNT(*) as count FROM invites")
        stats['invites_count'] = cursor.fetchone()['count']
        
        # Количество ожидающих приглашений
        cursor.execute("SELECT COUNT(*) as count FROM invites WHERE status = 'pending'")
        stats['pending_invites_count'] = cursor.fetchone()['count']
        
        # Количество элементов в очереди
        cursor.execute("SELECT COUNT(*) as count FROM parsequeue")
        stats['queue_items_count'] = cursor.fetchone()['count']
        
        # Количество ожидающих в очереди
        cursor.execute("SELECT COUNT(*) as count FROM parsequeue WHERE status = %s", (STATUS_PENDING,))
        stats['pending_queue_count'] = cursor.fetchone()['count']
        
        # Количество готовых отчётов
        cursor.execute("SELECT COUNT(*) as count FROM cards")
        stats['cards_count'] = cursor.fetchone()['count']
        
        # Количество отчётов с файлами
        cursor.execute("SELECT COUNT(*) as count FROM cards WHERE report_path IS NOT NULL")
        stats['completed_reports_count'] = cursor.fetchone()['count']
        
        return stats
    
    # ===== SUPERADMIN METHODS =====
    
    def is_superadmin(self, user_id: str) -> bool:
        """Проверить, является ли пользователь суперадмином"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT is_superadmin FROM users WHERE id = %s", (user_id,))
        row = cursor.fetchone()
        if not row:
            return False

        # Безопасная обработка sqlite3.Row или tuple
        try:
            if hasattr(row, "keys"):
                # sqlite3.Row
                if "is_superadmin" in row.keys():
                    return bool(row["is_superadmin"])
                # Если по какой‑то причине колонки нет — считаем, что не суперадмин
                return False
            else:
                # tuple/list — берём первый столбец
                return bool(row[0]) if len(row) > 0 else False
        except Exception as e:
            print(f"❌ Ошибка проверки is_superadmin: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def set_superadmin(self, user_id: str, is_superadmin: bool = True):
        """Установить статус суперадмина для пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE users 
            SET is_superadmin = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (is_superadmin, user_id))
        self.conn.commit()
    
    # ===== BUSINESSES =====
    
    def create_business(self, name: str, description: str = None, industry: str = None, owner_id: str = None, 
                       business_type: str = None, address: str = None, working_hours: str = None,
                       phone: str = None, email: str = None, website: str = None, yandex_url: str = None,
                       city: str = None, country: str = 'US', moderation_status: str = 'pending') -> str:
        """Создать новый бизнес"""
        if not owner_id:
            raise ValueError("owner_id обязателен для создания бизнеса")
        
        business_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        try:
            # Для Postgres предполагаем, что все необходимые поля уже существуют (schema_postgres.sql).
            fields = [
                "id",
                "name",
                "description",
                "industry",
                "business_type",
                "address",
                "working_hours",
                "phone",
                "email",
                "website",
                "owner_id",
                "yandex_url",
                "city",
                "country",
                "moderation_status",
            ]
            values = [
                business_id,
                name,
                description,
                industry,
                business_type,
                address,
                working_hours,
                phone,
                email,
                website,
                owner_id,
                yandex_url,
                city,
                country,
                moderation_status,
            ]

            fields_str = ", ".join(fields)
            placeholders = ", ".join(["%s"] * len(fields))

            cursor.execute(
                f"""
                INSERT INTO businesses ({fields_str})
                VALUES ({placeholders})
            """,
                values,
            )
            # НЕ коммитим здесь - вызывающий код должен сделать commit
            return business_id
        except Exception as e:
            # Откатываем при ошибке
            self.conn.rollback()
            raise
    
    def get_all_businesses(self) -> List[Dict[str, Any]]:
        """Получить все бизнесы (только для суперадмина) - только активные"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT b.*, u.email as owner_email, u.name as owner_name
            FROM businesses b
            LEFT JOIN users u ON b.owner_id = u.id
            WHERE b.is_active = TRUE OR b.is_active IS NULL
            ORDER BY b.created_at DESC
        """)
        rows = cursor.fetchall()
        # Преобразуем sqlite3.Row в словари
        result = []
        for row in rows:
            if hasattr(row, 'keys'):
                # Это sqlite3.Row
                result.append({key: row[key] for key in row.keys()})
            else:
                # Это tuple - преобразуем в dict по описанию колонок
                columns = [desc[0] for desc in cursor.description]
                result.append(dict(zip(columns, row)))
        return result
    
    def get_businesses_by_owner(self, owner_id: str) -> List[Dict[str, Any]]:
        """Получить бизнесы конкретного владельца (только прямые, без сетей)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM businesses 
            WHERE owner_id = %s AND is_active = TRUE
            ORDER BY created_at DESC
        """, (owner_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_businesses_by_network_owner(self, owner_id: str) -> List[Dict[str, Any]]:
        """Получить бизнесы владельца сети: свои личные + бизнесы из сетей - только активные"""
        cursor = self.conn.cursor()
        
        # Получаем бизнесы, которые напрямую принадлежат пользователю
        cursor.execute("""
            SELECT * FROM businesses 
            WHERE owner_id = %s AND (is_active = TRUE OR is_active IS NULL)
            ORDER BY created_at DESC
        """, (owner_id,))
        direct_businesses = [dict(row) for row in cursor.fetchall()]
        
        # Получаем бизнесы из сетей, которыми владеет пользователь
        cursor.execute("""
            SELECT b.* 
            FROM businesses b
            INNER JOIN networks n ON b.network_id = n.id
            WHERE n.owner_id = %s AND (b.is_active = TRUE OR b.is_active IS NULL)
            ORDER BY b.created_at DESC
        """, (owner_id,))
        network_businesses = [dict(row) for row in cursor.fetchall()]
        
        # Объединяем и убираем дубликаты
        all_businesses = {}
        for business in direct_businesses + network_businesses:
            all_businesses[business['id']] = business
        
        return list(all_businesses.values())
    
    def is_network_owner(self, user_id: str) -> bool:
        """Проверить, является ли пользователь владельцем хотя бы одной сети"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT COUNT(*) FROM networks WHERE owner_id = %s
        """, (user_id,))
        row = cursor.fetchone()
        count = row[0] if not hasattr(row, "keys") else row.get("count", 0)
        return (count or 0) > 0
    
    def create_network(self, name: str, owner_id: str, description: str = None) -> str:
        """Создать новую сеть"""
        network_id = str(uuid.uuid4())
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO networks (id, name, owner_id, description, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (network_id, name, owner_id, description, datetime.now().isoformat(), datetime.now().isoformat()))
        self.conn.commit()
        return network_id
    
    def get_user_networks(self, owner_id: str) -> List[Dict[str, Any]]:
        """Получить все сети пользователя"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM networks 
            WHERE owner_id = %s 
            ORDER BY created_at DESC
        """, (owner_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def add_business_to_network(self, business_id: str, network_id: str) -> bool:
        """Добавить бизнес в сеть"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE businesses 
            SET network_id = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (network_id, business_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def remove_business_from_network(self, business_id: str) -> bool:
        """Удалить бизнес из сети"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE businesses 
            SET network_id = NULL, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (business_id,))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_businesses_by_network(self, network_id: str) -> List[Dict[str, Any]]:
        """Получить все бизнесы (точки) сети - включая заблокированные.
        Возвращает список словарей с именами колонок (совместимо со схемой businesses)."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM businesses
            WHERE network_id = %s
            ORDER BY created_at DESC
        """, (network_id,))
        cols = [d[0] for d in cursor.description] if cursor.description else []
        rows = cursor.fetchall()
        return [dict(zip(cols, row)) for row in rows]
    
    def get_all_users_with_businesses(self) -> List[Dict[str, Any]]:
        """Получить всех пользователей с их бизнесами и сетями (для админской страницы)
        
        Оптимизировано: вместо N+1 запросов используется один запрос с JOIN и группировка в Python
        """
        cursor = self.conn.cursor()

        # Получаем всех пользователей одним запросом
        cursor.execute("""
            SELECT id, email, name, phone, created_at, is_active, is_verified, is_superadmin
            FROM users 
            ORDER BY created_at DESC
        """)
        user_cols = [d[0] for d in cursor.description]
        users = []
        for row in cursor.fetchall():
            if hasattr(row, "keys"):
                users.append({k: row[k] for k in row.keys()})
            else:
                users.append(dict(zip(user_cols, row)))

        # Временный лог формата строк (dev/debug)
        if users:
            print(
                "🔍 DEBUG get_all_users_with_businesses: users row "
                f"type={type(users[0])}, keys={list(users[0].keys())}"
            )
        
        # Все прямые бизнесы (не в сети)
        cursor.execute("""
            SELECT * FROM businesses 
            WHERE network_id IS NULL
            ORDER BY owner_id, created_at DESC
        """)
        biz_cols = [d[0] for d in cursor.description]
        all_direct_businesses = []
        for row in cursor.fetchall():
            if hasattr(row, "keys"):
                all_direct_businesses.append({k: row[k] for k in row.keys()})
            else:
                all_direct_businesses.append(dict(zip(biz_cols, row)))

        if all_direct_businesses:
            print(
                "🔍 DEBUG get_all_users_with_businesses: businesses row "
                f"keys={list(all_direct_businesses[0].keys())}"
            )

        # Все сети
        cursor.execute("""
            SELECT * FROM networks 
            ORDER BY owner_id, created_at DESC
        """)
        net_cols = [d[0] for d in cursor.description]
        all_networks = []
        for row in cursor.fetchall():
            if hasattr(row, "keys"):
                all_networks.append({k: row[k] for k in row.keys()})
            else:
                all_networks.append(dict(zip(net_cols, row)))

        if all_networks:
            print(
                "🔍 DEBUG get_all_users_with_businesses: networks row "
                f"keys={list(all_networks[0].keys())}"
            )

        # Все бизнесы в сетях
        cursor.execute("""
            SELECT * FROM businesses 
            WHERE network_id IS NOT NULL
            ORDER BY network_id, created_at DESC
        """)
        nbiz_cols = [d[0] for d in cursor.description]
        all_network_businesses = []
        for row in cursor.fetchall():
            if hasattr(row, "keys"):
                all_network_businesses.append({k: row[k] for k in row.keys()})
            else:
                all_network_businesses.append(dict(zip(nbiz_cols, row)))
        
        # Группируем бизнесы по owner_id
        businesses_by_owner = {}
        for business in all_direct_businesses:
            owner_id = business.get('owner_id')
            if owner_id:
                if owner_id not in businesses_by_owner:
                    businesses_by_owner[owner_id] = []
                businesses_by_owner[owner_id].append(business)
        
        # Группируем сети по owner_id
        networks_by_owner = {}
        for network in all_networks:
            owner_id = network.get('owner_id')
            if owner_id:
                if owner_id not in networks_by_owner:
                    networks_by_owner[owner_id] = []
                networks_by_owner[owner_id].append(network)
        
        # Группируем бизнесы в сетях по network_id
        businesses_by_network = {}
        for business in all_network_businesses:
            network_id = business.get('network_id')
            if network_id:
                if network_id not in businesses_by_network:
                    businesses_by_network[network_id] = []
                businesses_by_network[network_id].append(business)
        
        # Формируем результат
        result = []
        for user_dict in users:
            user_id = user_dict.get('id')
            
            # Получаем прямые бизнесы пользователя
            direct_businesses = businesses_by_owner.get(user_id, [])
            # Логируем для отладки
            blocked_count = sum(1 for b in direct_businesses if b.get('is_active') == 0)
            if blocked_count > 0:
                print(f"🔍 DEBUG: Пользователь {user_id} имеет {blocked_count} заблокированных бизнесов из {len(direct_businesses)} всего")
            
            # Получаем сети пользователя
            networks = networks_by_owner.get(user_id, [])
            
            # Для каждой сети получаем её точки (бизнесы)
            networks_with_businesses = []
            for network in networks:
                network_id = network['id']
                network_businesses = businesses_by_network.get(network_id, [])
                networks_with_businesses.append({
                    **network,
                    'businesses': network_businesses
                })
            
            result.append({
                **user_dict,
                'direct_businesses': direct_businesses,
                'networks': networks_with_businesses
            })
        
        # Находим бизнесы без владельцев (orphan businesses) - включая заблокированные
        cursor.execute("""
            SELECT b.*
            FROM businesses b
            LEFT JOIN users u ON b.owner_id = u.id
            WHERE b.network_id IS NULL
            AND b.owner_id IS NOT NULL
            AND u.id IS NULL
            ORDER BY b.created_at DESC
        """)
        orphan_businesses = [dict(row) for row in cursor.fetchall()]
        
        # Добавляем специальную запись для бизнесов без владельцев
        if orphan_businesses:
            result.append({
                'id': None,
                'email': '[Без владельца]',
                'name': '[Бизнесы без владельца]',
                'phone': None,
                'created_at': None,
                'is_active': None,
                'is_verified': None,
                'is_superadmin': False,
                'direct_businesses': orphan_businesses,
                'networks': []
            })
            
        # Находим сети без владельцев (orphan networks)
        cursor.execute("""
            SELECT n.*
            FROM networks n
            LEFT JOIN users u ON n.owner_id = u.id
            WHERE u.id IS NULL
            ORDER BY n.created_at DESC
        """)
        orphan_networks = [dict(row) for row in cursor.fetchall()]
        
        if orphan_networks:
            # Для каждой сиротливой сети собираем её бизнесы
            networks_with_businesses = []
            for network in orphan_networks:
                network_id = network['id']
                # Ищем бизнесы этой сети (используем уже полученные all_network_businesses)
                # Это эффективнее чем делать новый запрос
                network_businesses = businesses_by_network.get(network_id, [])
                networks_with_businesses.append({
                    **network,
                    'businesses': network_businesses
                })
            
            # Если уже есть группа "Без владельца", добавляем туда
            found_orphan_group = False
            for user_group in result:
                if user_group['id'] is None and user_group['email'] == '[Без владельца]':
                    user_group['networks'].extend(networks_with_businesses)
                    found_orphan_group = True
                    break
            
            # Если группы нет, создаем её
            if not found_orphan_group:
                result.append({
                    'id': None,
                    'email': '[Без владельца]',
                    'name': '[Сети без владельца]',
                    'phone': None,
                    'created_at': None,
                    'is_active': None,
                    'is_verified': None,
                    'is_superadmin': False,
                    'direct_businesses': [],
                    'networks': networks_with_businesses
                })
        
        return result
    
    def get_business_by_id(self, business_id: str) -> Optional[Dict[str, Any]]:
        """Получить бизнес по ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM businesses WHERE id = %s", (business_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))
    
    def update_business(self, business_id: str, name: str = None, description: str = None, industry: str = None):
        """Обновить информацию о бизнесе"""
        cursor = self.conn.cursor()
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = %s")
            params.append(name)
        if description is not None:
            updates.append("description = %s")
            params.append(description)
        if industry is not None:
            updates.append("industry = %s")
            params.append(industry)
        
        if updates:
            updates.append("updated_at = CURRENT_TIMESTAMP")
            params.append(business_id)
            cursor.execute(
                f"""
                UPDATE businesses 
                SET {', '.join(updates)}
                WHERE id = %s
            """,
                params,
            )
            self.conn.commit()
    
    def delete_business(self, business_id: str):
        """Удалить бизнес навсегда (реальное удаление)"""
        cursor = self.conn.cursor()
        
        # Проверяем, существует ли бизнес
        cursor.execute("SELECT id, name FROM businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()
        if not business:
            print(f"❌ Бизнес с ID {business_id} не найден")
            return False
        
        biz_name = business.get('name') if hasattr(business, 'get') else (business[1] if len(business) > 1 else 'N/A')
        print(f"🔍 Удаление бизнеса: ID={business_id}, name={biz_name}")
        
        # Удаляем связанные данные
        cursor.execute("DELETE FROM userservices WHERE business_id = %s", (business_id,))
        deleted_services = cursor.rowcount
        cursor.execute("DELETE FROM financialtransactions WHERE business_id = %s", (business_id,))
        deleted_transactions = cursor.rowcount
        cursor.execute("DELETE FROM businessmaplinks WHERE business_id = %s", (business_id,))
        deleted_links = cursor.rowcount
        cursor.execute("DELETE FROM cards WHERE business_id = %s", (business_id,))
        deleted_results = cursor.rowcount
        cursor.execute("DELETE FROM parsequeue WHERE business_id = %s", (business_id,))
        deleted_queue = cursor.rowcount
        cursor.execute("DELETE FROM telegrambindtokens WHERE business_id = %s", (business_id,))
        deleted_tokens = cursor.rowcount
        
        print(f"🔍 Удалено связанных данных: services={deleted_services}, transactions={deleted_transactions}, links={deleted_links}, results={deleted_results}, queue={deleted_queue}, tokens={deleted_tokens}")
        
        # Удаляем сам бизнес
        cursor.execute("DELETE FROM businesses WHERE id = %s", (business_id,))
        deleted_count = cursor.rowcount
        self.conn.commit()
        
        print(f"🔍 Удалено бизнесов: {deleted_count}")
        
        return deleted_count > 0
    
    def block_business(self, business_id: str, is_blocked: bool = True):
        """Заблокировать/разблокировать бизнес"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE businesses 
            SET is_active = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (not is_blocked, business_id))  # is_active = TRUE если не заблокирован
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_services_by_business(self, business_id: str):
        """Получить услуги конкретного бизнеса"""
        cursor = self.conn.cursor()
        
        # Проверяем, есть ли поле business_id в таблице UserServices
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'public' AND table_name = 'userservices'
        """)
        columns = [row['column_name'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        
        if 'business_id' in columns:
            # Используем business_id для фильтрации
            cursor.execute("""
                SELECT id, name, description, category, keywords, price, created_at, updated_at
                FROM userservices 
                WHERE business_id = %s AND is_active = TRUE
                ORDER BY created_at DESC
            """, (business_id,))
        else:
            # Fallback: получаем owner_id бизнеса и выбираем услуги по user_id
            cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (business_id,))
            row = cursor.fetchone()
            owner_id = row['owner_id'] if isinstance(row, dict) else (row[0] if row else None)
            if not owner_id:
                return []
            cursor.execute("""
                SELECT id, name, description, category, keywords, price, created_at, updated_at
                FROM userservices 
                WHERE user_id = %s AND is_active = TRUE
                ORDER BY created_at DESC
            """, (owner_id,))
        
        columns = [description[0] for description in cursor.description]
        services = []
        for row in cursor.fetchall():
            service = dict(zip(columns, row))
            services.append(service)
        
        return services
    
    def get_financial_data_by_business(self, business_id: str):
        """Получить финансовые данные конкретного бизнеса"""
        cursor = self.conn.cursor()
        
        # Создаем таблицу FinancialMetrics если её нет
        # Для Postgres таблица FinancialMetrics создаётся миграциями, здесь только читаем.
        cursor.execute("""
            SELECT id, amount, description, transaction_type, date, created_at
            FROM financialtransactions 
            WHERE business_id = %s 
            ORDER BY date DESC
        """, (business_id,))
        
        columns = [description[0] for description in cursor.description]
        transactions = []
        for row in cursor.fetchall():
            transaction = dict(zip(columns, row))
            transactions.append(transaction)
        
        # Получаем метрики
        cursor.execute("""
            SELECT id, metric_name, metric_value, period, created_at
            FROM financialmetrics 
            WHERE business_id = %s 
            ORDER BY created_at DESC
        """, (business_id,))
        
        columns = [description[0] for description in cursor.description]
        metrics = []
        for row in cursor.fetchall():
            metric = dict(zip(columns, row))
            metrics.append(metric)
        
        return {
            "transactions": transactions,
            "metrics": metrics
        }
    
    def get_reports_by_business(self, business_id: str):
        """Получить отчеты конкретного бизнеса (использует get_card_history_by_business)"""
        return self.get_card_history_by_business(business_id)

    # ===== PROSPECTING LEADS =====

    def get_all_leads(self) -> List[Dict[str, Any]]:
        """Получить все лиды"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM prospectingleads ORDER BY created_at DESC")
        return [dict(zip([d[0] for d in cursor.description], row)) for row in cursor.fetchall()]

    def save_lead(self, lead_data: Dict[str, Any]) -> str:
        """Сохранить лид (если уже есть google_id - обновить)"""
        cursor = self.conn.cursor()
        
        # Проверяем дубликат по google_id
        google_id = lead_data.get('google_id')
        if google_id:
            cursor.execute("SELECT id FROM prospectingleads WHERE google_id = %s", (google_id,))
            existing = cursor.fetchone()
            if existing:
                return existing[0]

        lead_id = str(uuid.uuid4())
        fields = ['id', 'name', 'address', 'phone', 'website', 'rating', 'reviews_count', 
                  'source_url', 'google_id', 'category', 'location', 'status']
        
        values = [lead_id]
        for f in fields[1:]:
            values.append(lead_data.get(f))
            
        placeholders = ', '.join(['%s' for _ in values])
        
        cursor.execute(f"""
            INSERT INTO prospectingleads ({', '.join(fields)}, created_at, updated_at)
            VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, values)
        
        self.conn.commit()
        return lead_id

    def update_lead_status(self, lead_id: str, status: str) -> bool:
        """Обновить статус лида"""
        cursor = self.conn.cursor()
        cursor.execute("""
            UPDATE prospectingleads 
            SET status = %s, updated_at = CURRENT_TIMESTAMP 
            WHERE id = %s
        """, (status, lead_id))
        self.conn.commit()
        return cursor.rowcount > 0

    def delete_lead(self, lead_id: str) -> bool:
        """Удалить лид"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM prospectingleads WHERE id = %s", (lead_id,))
        self.conn.commit()
        return cursor.rowcount > 0

def main():
    """Основная функция для тестирования"""
    db = DatabaseManager()
    
    try:
        print("📊 Статистика системы:")
        stats = db.get_statistics()
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        print("\n👥 Пользователи:")
        users = db.get_all_users()
        for user in users[:5]:  # Показываем первых 5
            print(f"  {user['email']} - {user['name'] or 'Без имени'}")
        
        print("\n📋 Очередь:")
        queue = db.get_all_queue_items()
        for item in queue[:5]:  # Показываем первых 5
            print(f"  {item['url']} - {item['status']}")
        
        print("\n📄 Отчёты:")
        cards = db.get_all_cards()
        for card in cards[:5]:  # Показываем первых 5
            print(f"  {card['title'] or 'Без названия'} - {card['seo_score'] or 'Нет оценки'}")
        
    finally:
        db.close()

if __name__ == "__main__":
    main()
