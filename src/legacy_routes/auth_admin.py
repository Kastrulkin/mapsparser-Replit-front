from legacy_routes import shared as _shared

globals().update(_shared.runtime_namespace)

@app.route('/api/networks/<string:network_id>/stats', methods=['GET'])
def get_network_stats(network_id):
    """Получить статистику сети"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        period = request.args.get('period', 'month')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем доступ к сети
        cursor.execute("SELECT owner_id FROM networks WHERE id = %s", (network_id,))
        raw_network = cursor.fetchone()
        network = _row_to_dict(cursor, raw_network) if raw_network else None

        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404

        if network.get("owner_id") != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этой сети"}), 403

        # Получаем точки сети. Рейтинг/отзывы нужны как базовый источник для
        # демо-сетей и старых карточек без внешнего кеша метрик.
        business_columns_for_locations = _table_columns(cursor, "businesses")
        location_fields = ["id", "name"]
        for optional_field in ("rating", "reviews_count", "updated_at"):
            if optional_field in business_columns_for_locations:
                location_fields.append(optional_field)
        cursor.execute(
            f"SELECT {', '.join(location_fields)} FROM businesses WHERE network_id = %s",
            (network_id,),
        )
        raw_locations = cursor.fetchall()
        locations = [_row_to_dict(cursor, row) for row in raw_locations]
        location_ids = [loc.get("id") for loc in locations if loc.get("id")]

        if not location_ids:
            db.close()
            return jsonify({
                "success": True,
                "stats": {
                    "total_revenue": 0,
                    "total_orders": 0,
                    "locations_count": 0,
                    "by_services": [],
                    "by_masters": [],
                    "by_locations": [],
                    "ratings": [],
                    "bad_reviews": []
                }
            })

        # Вычисляем период
        if not start_date or not end_date:
            from datetime import datetime, timedelta
            now = datetime.now()

            if period == 'week':
                start_date = (now - timedelta(days=7)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'month':
                start_date = (now - timedelta(days=30)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'quarter':
                start_date = (now - timedelta(days=90)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')
            elif period == 'year':
                start_date = (now - timedelta(days=365)).strftime('%Y-%m-%d')
                end_date = now.strftime('%Y-%m-%d')

        # Получаем транзакции всех точек сети
        # Проверяем наличие поля business_id
        columns = _table_columns(cursor, "financialtransactions")
        has_business_id = 'business_id' in columns

        if has_business_id and location_ids:
            placeholders = ','.join(['%s'] * len(location_ids))
            cursor.execute(f"""
                SELECT services, amount, master_id, business_id
                FROM financialtransactions
                WHERE business_id IN ({placeholders}) AND transaction_date BETWEEN %s AND %s
            """, tuple(location_ids + [start_date, end_date]))
        else:
            # Если business_id нет, получаем через user_id владельца сети
            cursor.execute("""
                SELECT services, amount, master_id, NULL as business_id
                FROM financialtransactions
                WHERE user_id = %s AND transaction_date BETWEEN %s AND %s
            """, (network.get("owner_id"), start_date, end_date))

        transactions = cursor.fetchall()

        # Агрегируем данные
        services_revenue = {}
        masters_revenue = {}
        locations_revenue = {(loc.get("name") or "Неизвестно"): 0 for loc in locations}

        def _network_table_exists(table_name):
            cursor.execute("SELECT to_regclass(%s) AS table_name", (f"public.{str(table_name).lower()}",))
            table_row = cursor.fetchone()
            table_data = _row_to_dict(cursor, table_row) if table_row else {}
            return bool(table_data.get("table_name"))

        has_masters_table = _network_table_exists("masters")

        for row in transactions:
            row_data = _row_to_dict(cursor, row) if row else {}
            services_json = row_data.get("services")
            amount = float(row_data.get("amount") or 0)
            master_id = row_data.get("master_id")
            business_id = row_data.get("business_id")

            # По услугам
            if services_json:
                try:
                    services = json.loads(services_json) if isinstance(services_json, str) else services_json
                    if isinstance(services, list):
                        service_amount = amount / len(services) if len(services) > 0 else amount
                        for service in services:
                            service_name = service.strip() if isinstance(service, str) else str(service)
                            if service_name:
                                services_revenue[service_name] = services_revenue.get(service_name, 0) + service_amount
                except:
                    pass

            # По мастерам
            if master_id:
                if has_masters_table:
                    cursor.execute("SELECT name FROM masters WHERE id = %s", (master_id,))
                    master_row = cursor.fetchone()
                    master_dict = _row_to_dict(cursor, master_row) if master_row else None
                    master_name = master_dict.get("name") if master_dict else f"Мастер {master_id[:8]}"
                else:
                    master_name = f"Мастер {str(master_id)[:8]}"
                masters_revenue[master_name] = masters_revenue.get(master_name, 0) + amount

            # По точкам
            location_name = next((loc.get("name") for loc in locations if loc.get("id") == business_id), "Неизвестно")
            locations_revenue[location_name] = locations_revenue.get(location_name, 0) + amount

        # Преобразуем в массивы
        by_services = [{"name": name, "value": round(value, 2)} for name, value in services_revenue.items()]
        by_masters = [{"name": name, "value": round(value, 2)} for name, value in masters_revenue.items()]
        by_locations = [{"name": name, "value": round(value, 2)} for name, value in locations_revenue.items()]

        by_services.sort(key=lambda x: x['value'], reverse=True)
        by_masters.sort(key=lambda x: x['value'], reverse=True)
        by_locations.sort(key=lambda x: x['value'], reverse=True)

        # Рейтинги и отзывы по данным Яндекс.Карт (если есть кеш-поля)
        ratings = []
        try:
            business_columns = _table_columns(cursor, "businesses")
            has_yandex_cache = {
                "yandex_rating",
                "yandex_reviews_total",
                "yandex_reviews_30d",
                "yandex_last_sync",
            }.issubset(business_columns)
            if has_yandex_cache:
                cursor.execute(
                    """
                    SELECT id, name, yandex_rating, yandex_reviews_total, yandex_reviews_30d, yandex_last_sync
                    FROM businesses
                    WHERE network_id = %s AND (is_active = TRUE OR is_active = 1 OR is_active IS NULL)
                    """,
                    (network_id,),
                )
                for row in cursor.fetchall():
                    row_data = _row_to_dict(cursor, row) if row else {}
                    ratings.append(
                        {
                            "business_id": row_data.get("id"),
                            "name": row_data.get("name"),
                            "rating": row_data.get("yandex_rating"),
                            "reviews_total": row_data.get("yandex_reviews_total"),
                            "reviews_30d": row_data.get("yandex_reviews_30d"),
                            "last_sync": row_data.get("yandex_last_sync"),
                        }
                    )
            else:
                has_external_stats = _network_table_exists("externalbusinessstats")
                has_map_parse = _network_table_exists("mapparseresults")
                if has_external_stats and has_map_parse:
                    rating_sql = """
                        SELECT b.id, b.name,
                               COALESCE(es.rating, b.rating, NULLIF(mpr.rating, '')::DOUBLE PRECISION) AS rating,
                               COALESCE(es.reviews_total, b.reviews_count, mpr.reviews_count) AS reviews_total,
                               0 AS reviews_30d,
                               COALESCE(es.updated_at, mpr.created_at, b.updated_at) AS last_sync
                        FROM businesses b
                        LEFT JOIN LATERAL (
                            SELECT rating, reviews_total, updated_at
                            FROM externalbusinessstats
                            WHERE business_id = b.id
                            ORDER BY date DESC, updated_at DESC
                            LIMIT 1
                        ) es ON TRUE
                        LEFT JOIN LATERAL (
                            SELECT rating, reviews_count, created_at
                            FROM mapparseresults
                            WHERE business_id = b.id
                            ORDER BY created_at DESC
                            LIMIT 1
                        ) mpr ON TRUE
                        WHERE b.network_id = %s AND (b.is_active = TRUE OR b.is_active = 1 OR b.is_active IS NULL)
                    """
                elif has_external_stats:
                    rating_sql = """
                        SELECT b.id, b.name,
                               COALESCE(es.rating, b.rating) AS rating,
                               COALESCE(es.reviews_total, b.reviews_count) AS reviews_total,
                               0 AS reviews_30d,
                               COALESCE(es.updated_at, b.updated_at) AS last_sync
                        FROM businesses b
                        LEFT JOIN LATERAL (
                            SELECT rating, reviews_total, updated_at
                            FROM externalbusinessstats
                            WHERE business_id = b.id
                            ORDER BY date DESC, updated_at DESC
                            LIMIT 1
                        ) es ON TRUE
                        WHERE b.network_id = %s AND (b.is_active = TRUE OR b.is_active = 1 OR b.is_active IS NULL)
                    """
                elif has_map_parse:
                    rating_sql = """
                        SELECT b.id, b.name,
                               COALESCE(b.rating, NULLIF(mpr.rating, '')::DOUBLE PRECISION) AS rating,
                               COALESCE(b.reviews_count, mpr.reviews_count) AS reviews_total,
                               0 AS reviews_30d,
                               COALESCE(mpr.created_at, b.updated_at) AS last_sync
                        FROM businesses b
                        LEFT JOIN LATERAL (
                            SELECT rating, reviews_count, created_at
                            FROM mapparseresults
                            WHERE business_id = b.id
                            ORDER BY created_at DESC
                            LIMIT 1
                        ) mpr ON TRUE
                        WHERE b.network_id = %s AND (b.is_active = TRUE OR b.is_active = 1 OR b.is_active IS NULL)
                    """
                else:
                    rating_sql = """
                        SELECT b.id, b.name, b.rating, b.reviews_count AS reviews_total,
                               0 AS reviews_30d, b.updated_at AS last_sync
                        FROM businesses b
                        WHERE b.network_id = %s AND (b.is_active = TRUE OR b.is_active = 1 OR b.is_active IS NULL)
                    """
                cursor.execute(rating_sql, (network_id,))
                for row in cursor.fetchall():
                    row_data = _row_to_dict(cursor, row) if row else {}
                    ratings.append(
                        {
                            "business_id": row_data.get("id"),
                            "name": row_data.get("name"),
                            "rating": row_data.get("rating"),
                            "reviews_total": row_data.get("reviews_total"),
                            "reviews_30d": row_data.get("reviews_30d"),
                            "last_sync": row_data.get("last_sync"),
                        }
                    )
        except Exception as ratings_error:
            print(f"⚠️ Не удалось собрать рейтинги сети: {ratings_error}")
            ratings = []

        if not ratings:
            try:
                for loc in locations:
                    if loc.get("rating") is None and loc.get("reviews_count") is None:
                        continue
                    ratings.append(
                        {
                            "business_id": loc.get("id"),
                            "name": loc.get("name"),
                            "rating": loc.get("rating"),
                            "reviews_total": loc.get("reviews_count"),
                            "reviews_30d": 0,
                            "last_sync": loc.get("updated_at"),
                        }
                    )
                if not ratings:
                    cursor.execute(
                        """
                        SELECT id, name, rating, reviews_count AS reviews_total, 0 AS reviews_30d, updated_at AS last_sync
                        FROM businesses
                        WHERE network_id = %s AND (is_active = TRUE OR is_active = 1 OR is_active IS NULL)
                        ORDER BY name
                        """,
                        (network_id,),
                    )
                    for row in cursor.fetchall():
                        row_data = _row_to_dict(cursor, row) if row else {}
                        ratings.append(
                            {
                                "business_id": row_data.get("id"),
                                "name": row_data.get("name"),
                                "rating": row_data.get("rating"),
                                "reviews_total": row_data.get("reviews_total"),
                                "reviews_30d": row_data.get("reviews_30d"),
                                "last_sync": row_data.get("last_sync"),
                            }
                        )
            except Exception as ratings_fallback_error:
                print(f"⚠️ Не удалось собрать fallback рейтинги сети: {ratings_fallback_error}")
                ratings = []

        bad_reviews = []

        db.close()

        return jsonify({
            "success": True,
            "stats": {
                "total_revenue": sum(locations_revenue.values()),
                "total_orders": len(transactions),
                "locations_count": len(locations),
                "by_services": by_services,
                "by_masters": by_masters,
                "by_locations": by_locations,
                "ratings": ratings,
                "bad_reviews": bad_reviews
            }
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка получения статистики сети: {str(e)}"}), 500

@app.route('/api/admin/yandex/sync/<string:network_id>', methods=['POST'])
def admin_sync_network_yandex(network_id):
    """
    Ручной запуск синхронизации Яндекс-данных для сети.
    Требует действующей сессии и прав суперадмина или владельца сети.
    """
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("SELECT owner_id FROM networks WHERE id = %s", (network_id,))
        raw_network = cursor.fetchone()
        network = _row_to_dict(cursor, raw_network) if raw_network else None

        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404

        if network.get("owner_id") != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этой сети"}), 403

        db.close()

        if YandexSyncService is None:
            return jsonify({"error": "YandexSyncService не доступен. Проверьте логи сервера."}), 500

        try:
            sync_service = YandexSyncService()
            synced_count = sync_service.sync_network(network_id)
        except Exception as e:
            import traceback
            print(f"❌ Ошибка при синхронизации сети {network_id}: {e}")
            traceback.print_exc()
            return jsonify({"error": f"Ошибка синхронизации: {str(e)}"}), 500

        return jsonify(
            {
                "success": True,
                "synced_count": synced_count,
                "message": f"Обновлено бизнесов: {synced_count}",
            }
        )
    except Exception as e:
        return jsonify({"error": f"Ошибка синхронизации Яндекс для сети: {str(e)}"}), 500

@app.route('/api/admin/yandex/sync/business/<string:business_id>', methods=['POST'])
def admin_sync_business_yandex(business_id):
    """
    Ручной запуск синхронизации Яндекс-данных для одного бизнеса.
    Требует действующей сессии и прав суперадмина или владельца бизнеса.
    """
    import traceback
    print(f"🔄 Запрос на синхронизацию бизнеса {business_id}")
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("SELECT owner_id, name FROM businesses WHERE id = %s", (business_id,))
        raw_business = cursor.fetchone()
        business = _row_to_dict(cursor, raw_business) if raw_business else None

        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        business_owner_id = business.get("owner_id")
        business_name = (business.get("name") or "").strip() or "Unknown"

        if business_owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        cursor.execute(
            """
            SELECT status, created_at
            FROM parsequeue
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        raw_latest_queue = cursor.fetchone()
        latest_queue = _row_to_dict(cursor, raw_latest_queue) if raw_latest_queue else None
        latest_queue_status = _normalize_existing_queue_status(latest_queue)
        if latest_queue_status in ("pending", "queued", "processing", "captcha"):
            db.close()
            return jsonify({
                "success": False,
                "error": "Обновление уже запущено",
                "message": "Сейчас уже идёт сбор данных. Дождитесь завершения текущего обновления."
            }), 409

        cursor.execute(
            """
            SELECT created_at
            FROM parsequeue
            WHERE business_id = %s
              AND status IN ('completed', 'done')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        raw_last_completed = cursor.fetchone()
        last_completed_row = _row_to_dict(cursor, raw_last_completed) if raw_last_completed else None
        last_completed_at_raw = (last_completed_row or {}).get("created_at")
        last_completed_at = None
        if last_completed_at_raw:
            try:
                last_completed_at = datetime.fromisoformat(str(last_completed_at_raw).replace("Z", "+00:00"))
                if last_completed_at.tzinfo is not None:
                    last_completed_at = last_completed_at.astimezone().replace(tzinfo=None)
            except ValueError:
                last_completed_at = None

        if not last_completed_at:
            cursor.execute("SELECT last_parsed_at FROM businesses WHERE id = %s", (business_id,))
            raw_last_parsed = cursor.fetchone()
            last_parsed_row = _row_to_dict(cursor, raw_last_parsed) if raw_last_parsed else None
            last_parsed_at_raw = (last_parsed_row or {}).get("last_parsed_at")
            if last_parsed_at_raw:
                try:
                    last_completed_at = datetime.fromisoformat(str(last_parsed_at_raw).replace("Z", "+00:00"))
                    if last_completed_at.tzinfo is not None:
                        last_completed_at = last_completed_at.astimezone().replace(tzinfo=None)
                except ValueError:
                    last_completed_at = None

        cursor.execute("SELECT to_regclass('public.invites') AS invites_table")
        raw_invites_table = cursor.fetchone()
        invites_table_row = _row_to_dict(cursor, raw_invites_table) if raw_invites_table else None
        invites_table_exists = bool((invites_table_row or {}).get("invites_table"))

        accepted_invites_count = 0
        if business_owner_id and invites_table_exists:
            cursor.execute(
                """
                SELECT COUNT(*) AS accepted_count
                FROM invites
                WHERE invited_by = %s
                  AND status = 'accepted'
                """,
                (business_owner_id,),
            )
            raw_invites = cursor.fetchone()
            invite_row = _row_to_dict(cursor, raw_invites) if raw_invites else None
            accepted_invites_count = int((invite_row or {}).get("accepted_count") or 0)

        if last_completed_at:
            cooldown_until = last_completed_at + timedelta(days=7)
            if cooldown_until > datetime.now() and accepted_invites_count <= 0:
                db.close()
                return jsonify({
                    "success": False,
                    "error": "Обновление пока недоступно",
                    "message": (
                        "Обновить данные карточки можно раз в неделю. "
                        f"Следующее обновление будет доступно после {cooldown_until.replace(microsecond=0).isoformat()}. "
                        "Если пригласить друга, обновление станет доступно раньше."
                    ),
                    "refresh_policy": {
                        "can_refresh": False,
                        "reason": "weekly_cooldown",
                        "cooldown_days": 7,
                        "last_completed_at": last_completed_at.replace(microsecond=0).isoformat(),
                        "cooldown_until": cooldown_until.replace(microsecond=0).isoformat(),
                        "invite_override_available": False,
                        "accepted_invites_count": accepted_invites_count,
                    },
                }), 429

        # Аккаунт Яндекс.Бизнес (таблица externalbusinessaccounts — Postgres)
        cursor.execute("""
            SELECT id, auth_data_encrypted, external_id
            FROM externalbusinessaccounts
            WHERE business_id = %s AND source = 'yandex_business' AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        raw_account = cursor.fetchone()
        account_row = _row_to_dict(cursor, raw_account) if raw_account else None
        account_id = account_row.get("id") if account_row else None

        if account_id:
            print(f"✅ Найден аккаунт: {account_id}")
        else:
            print(f"⚠️ Аккаунт Яндекс.Бизнес не найден")

        cursor.execute("SELECT url FROM businessmaplinks WHERE business_id = %s AND map_type = 'yandex' LIMIT 1", (business_id,))
        raw_map = cursor.fetchone()
        map_link_row = _row_to_dict(cursor, raw_map) if raw_map else None
        map_url = map_link_row.get("url") if map_link_row else None

        if not account_id and not map_url:
            db.close()
            return jsonify({
                "success": False,
                "error": "Не найден источник данных",
                "message": "Для запуска парсинга добавьте ссылку на Яндекс.Карты или подключите аккаунт Яндекс.Бизнес"
            }), 400

        task_id = str(uuid.uuid4())
        user_id = user_data["user_id"]

        if map_url:
            task_type = 'parse_card'
            use_apify_map_parsing = bool(get_use_apify_map_parsing(db.conn))
            source = resolve_map_source_for_queue('yandex_maps', use_apify_map_parsing)
            target_url = map_url
            message = "Собираем данные. Это может занять несколько минут."
        else:
            task_type = 'sync_yandex_business'
            source = 'yandex_business'
            target_url = ''
            message = "Запущена синхронизация (без парсинга)"

        cursor.execute("""
            INSERT INTO parsequeue (
                id, business_id, account_id, task_type, source,
                status, user_id, url, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s,
                    'pending', %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (task_id, business_id, account_id, task_type, source, user_id, target_url))
        db.conn.commit()
        db.close()
        print(f"✅ Задача {task_type} добавлена в очередь: {task_id}")

        return jsonify({
            "success": True,
            "message": message,
            "sync_id": task_id,
            "task_type": task_type
        })

    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ admin_sync_business_yandex: {e}\n{error_details}")
        payload = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }
        if getattr(app, "debug", False):
            payload["traceback"] = error_details
        return jsonify(payload), 500

@app.route('/api/admin/2gis/sync/business/<string:business_id>', methods=['POST'])
def admin_sync_business_2gis(business_id):
    """
    Ручной запуск синхронизации/парсинга 2ГИС для одного бизнеса.
    Приоритет:
      1) Если есть ссылка на 2ГИС в businessmaplinks -> task_type=parse_card, source=2gis
      2) Иначе, если есть активный external account 2gis -> task_type=sync_2gis
    """
    import traceback
    print(f"🔄 Запрос на синхронизацию 2ГИС бизнеса {business_id}")
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("SELECT owner_id, name FROM businesses WHERE id = %s", (business_id,))
        raw_business = cursor.fetchone()
        business = _row_to_dict(cursor, raw_business) if raw_business else None

        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        business_owner_id = business.get("owner_id")
        if business_owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        cursor.execute(
            """
            SELECT status, created_at
            FROM parsequeue
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        raw_latest_queue = cursor.fetchone()
        latest_queue = _row_to_dict(cursor, raw_latest_queue) if raw_latest_queue else None
        latest_queue_status = _normalize_existing_queue_status(latest_queue)
        if latest_queue_status in ("pending", "queued", "processing", "captcha"):
            db.close()
            return jsonify({
                "success": False,
                "error": "Обновление уже запущено",
                "message": "Сейчас уже идёт сбор данных. Дождитесь завершения текущего обновления."
            }), 409

        cursor.execute(
            """
            SELECT created_at
            FROM parsequeue
            WHERE business_id = %s
              AND status IN ('completed', 'done')
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        raw_last_completed = cursor.fetchone()
        last_completed_row = _row_to_dict(cursor, raw_last_completed) if raw_last_completed else None
        last_completed_at_raw = (last_completed_row or {}).get("created_at")
        last_completed_at = None
        if last_completed_at_raw:
            try:
                last_completed_at = datetime.fromisoformat(str(last_completed_at_raw).replace("Z", "+00:00"))
                if last_completed_at.tzinfo is not None:
                    last_completed_at = last_completed_at.astimezone().replace(tzinfo=None)
            except ValueError:
                last_completed_at = None

        if not last_completed_at:
            cursor.execute("SELECT last_parsed_at FROM businesses WHERE id = %s", (business_id,))
            raw_last_parsed = cursor.fetchone()
            last_parsed_row = _row_to_dict(cursor, raw_last_parsed) if raw_last_parsed else None
            last_parsed_at_raw = (last_parsed_row or {}).get("last_parsed_at")
            if last_parsed_at_raw:
                try:
                    last_completed_at = datetime.fromisoformat(str(last_parsed_at_raw).replace("Z", "+00:00"))
                    if last_completed_at.tzinfo is not None:
                        last_completed_at = last_completed_at.astimezone().replace(tzinfo=None)
                except ValueError:
                    last_completed_at = None

        cursor.execute("SELECT to_regclass('public.invites') AS invites_table")
        raw_invites_table = cursor.fetchone()
        invites_table_row = _row_to_dict(cursor, raw_invites_table) if raw_invites_table else None
        invites_table_exists = bool((invites_table_row or {}).get("invites_table"))

        accepted_invites_count = 0
        if business_owner_id and invites_table_exists:
            cursor.execute(
                """
                SELECT COUNT(*) AS accepted_count
                FROM invites
                WHERE invited_by = %s
                  AND status = 'accepted'
                """,
                (business_owner_id,),
            )
            raw_invites = cursor.fetchone()
            invite_row = _row_to_dict(cursor, raw_invites) if raw_invites else None
            accepted_invites_count = int((invite_row or {}).get("accepted_count") or 0)

        if last_completed_at:
            cooldown_until = last_completed_at + timedelta(days=7)
            if cooldown_until > datetime.now() and accepted_invites_count <= 0:
                db.close()
                return jsonify({
                    "success": False,
                    "error": "Обновление пока недоступно",
                    "message": (
                        "Обновить данные карточки можно раз в неделю. "
                        f"Следующее обновление будет доступно после {cooldown_until.replace(microsecond=0).isoformat()}. "
                        "Если пригласить друга, обновление станет доступно раньше."
                    ),
                    "refresh_policy": {
                        "can_refresh": False,
                        "reason": "weekly_cooldown",
                        "cooldown_days": 7,
                        "last_completed_at": last_completed_at.replace(microsecond=0).isoformat(),
                        "cooldown_until": cooldown_until.replace(microsecond=0).isoformat(),
                        "invite_override_available": False,
                        "accepted_invites_count": accepted_invites_count,
                    },
                }), 429

        cursor.execute(
            """
            SELECT id, auth_data_encrypted, external_id
            FROM externalbusinessaccounts
            WHERE business_id = %s AND source = '2gis' AND is_active = TRUE
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        raw_account = cursor.fetchone()
        account_row = _row_to_dict(cursor, raw_account) if raw_account else None
        account_id = account_row.get("id") if account_row else None

        cursor.execute(
            """
            SELECT url
            FROM businessmaplinks
            WHERE business_id = %s
              AND (
                map_type = '2gis'
                OR LOWER(url) LIKE '%%2gis.ru/%%'
                OR LOWER(url) LIKE '%%2gis.com/%%'
              )
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        raw_map = cursor.fetchone()
        map_row = _row_to_dict(cursor, raw_map) if raw_map else None
        map_url = (map_row.get("url") if map_row else None) or ""
        map_url = str(map_url).strip()

        if not map_url and not account_id:
            db.close()
            return jsonify(
                {
                    "success": False,
                    "error": "Не найден источник данных 2ГИС",
                    "message": "Добавьте ссылку на 2ГИС в Профиле или подключите аккаунт 2ГИС в интеграциях",
                }
            ), 400

        task_id = str(uuid.uuid4())
        user_id = user_data["user_id"]

        if map_url:
            task_type = "parse_card"
            use_apify_map_parsing = bool(get_use_apify_map_parsing(db.conn))
            source = resolve_map_source_for_queue("2gis", use_apify_map_parsing)
            target_url = map_url
            message = "Собираем данные. Это может занять несколько минут."
        else:
            task_type = "sync_2gis"
            source = "2gis"
            target_url = ""
            message = "Запущена синхронизация 2ГИС через API"

        cursor.execute(
            """
            INSERT INTO parsequeue (
                id, business_id, account_id, task_type, source,
                status, user_id, url, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, 'pending', %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """,
            (task_id, business_id, account_id, task_type, source, user_id, target_url),
        )
        db.conn.commit()
        db.close()

        print(f"✅ Задача {task_type} (2GIS) добавлена в очередь: {task_id}")
        return jsonify(
            {
                "success": True,
                "message": message,
                "sync_id": task_id,
                "task_type": task_type,
                "source": source,
            }
        )
    except Exception as e:
        error_details = traceback.format_exc()
        print(f"❌ admin_sync_business_2gis: {e}\n{error_details}")
        payload = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
        }
        if getattr(app, "debug", False):
            payload["traceback"] = error_details
        return jsonify(payload), 500

def _sync_yandex_business_sync_task(sync_id, business_id, account_id):
    """Внутренняя функция для выполнения синхронизации (вызывается из worker)"""
    if YandexBusinessParser is None:
        print("❌ YandexBusinessParser не доступен")
        return False

    db = DatabaseManager()
    cursor = db.conn.cursor()

    try:
        cursor.execute("""
            SELECT auth_data_encrypted, external_id
            FROM externalbusinessaccounts
            WHERE id = %s
        """, (account_id,))
        raw_account = cursor.fetchone()
        account_row = _row_to_dict(cursor, raw_account) if raw_account else None

        if not account_row:
            print(f"❌ Аккаунт {account_id} не найден")
            cursor.execute("""
                UPDATE parsequeue SET status = %s, error_message = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s
            """, (STATUS_ERROR, "Аккаунт не найден", sync_id))
            db.conn.commit()
            return False

        auth_data_encrypted = account_row.get("auth_data_encrypted")
        external_id = account_row.get("external_id")

        cursor.execute("SELECT name FROM businesses WHERE id = %s", (business_id,))
        raw_business = cursor.fetchone()
        business_row = _row_to_dict(cursor, raw_business) if raw_business else None
        business_name = (business_row.get("name") or "").strip() or "Unknown"

        db.close()

        # Расшифровываем auth_data
        print(f"🔐 Расшифровка auth_data для аккаунта {account_id}...")
        print(f"   Длина зашифрованных данных: {len(auth_data_encrypted) if auth_data_encrypted else 0} символов")
        auth_data_plain = decrypt_auth_data(auth_data_encrypted)
        if not auth_data_plain:
            print(f"❌ Не удалось расшифровать auth_data для аккаунта {account_id}")
            print(f"   Проверьте:")
            print(f"   1. Установлен ли EXTERNAL_AUTH_SECRET_KEY в .env (должен совпадать с ключом при шифровании)")
            print(f"   2. Установлена ли библиотека cryptography: pip install cryptography")
            print(f"   3. Правильный ли формат данных в БД")
            return False
        print(f"✅ auth_data успешно расшифрован (длина: {len(auth_data_plain)} символов)")

        # Парсим JSON auth_data
        import json
        try:
            auth_data_dict = json.loads(auth_data_plain)
        except json.JSONDecodeError:
            # Если не JSON, предполагаем что это просто cookies строка
            auth_data_dict = {"cookies": auth_data_plain}

        # Создаём парсер
        parser = YandexBusinessParser(auth_data_dict)

        # Получаем данные
        account_data = {
            "id": account_id,
            "business_id": business_id,
            "external_id": external_id
        }

        print(f"📥 Получение отзывов...")
        reviews = parser.fetch_reviews(account_data)
        print(f"✅ Получено отзывов: {len(reviews)}")

        print(f"📥 Получение статистики...")
        stats = parser.fetch_stats(account_data)
        print(f"✅ Получено точек статистики: {len(stats)}")

        print(f"📥 Получение публикаций...")
        posts = parser.fetch_posts(account_data)
        print(f"✅ Получено публикаций: {len(posts)}")

        # Получаем услуги/прайс-лист
        print(f"📥 Получение услуг/прайс-листа...")
        services = parser.fetch_services(account_data)
        print(f"✅ Получено услуг: {len(services)}")

        # Получаем информацию об организации (рейтинг, количество отзывов, новостей, фото)
        print(f"📥 Получение информации об организации...")
        org_info = parser.fetch_organization_info(account_data)
        print(f"✅ Информация об организации:")
        print(f"   Рейтинг: {org_info.get('rating')}")
        print(f"   Отзывов: {org_info.get('reviews_count')}")
        print(f"   Новостей: {org_info.get('news_count')}")
        print(f"   Фото: {org_info.get('photos_count')}")

        # Сохраняем данные
        db = DatabaseManager()
        worker = YandexBusinessSyncWorker()

        if reviews:
            worker._upsert_reviews(db, reviews)
            print(f"💾 Сохранено отзывов: {len(reviews)}")

        # Создаём статистику с информацией об организации, если её нет
        if not stats and org_info:
                from external_sources import ExternalStatsPoint, make_stats_id
                from datetime import date
                today_str = date.today().isoformat()
                stat_id = make_stats_id(business_id, "yandex_business", today_str)
                stat = ExternalStatsPoint(
                    id=stat_id,
                    business_id=business_id,
                    source="yandex_business",
                    date=today_str,
                    views_total=0,
                    clicks_total=0,
                    actions_total=0,
                    rating=org_info.get('rating'),
                    reviews_total=org_info.get('reviews_count') or len(reviews),
                    raw_payload=org_info,
                )
                stats = [stat]

        if stats:
            # Обновляем последнюю статистику информацией об организации
            if org_info and stats:
                last_stat = stats[-1]
                if last_stat.raw_payload:
                    last_stat.raw_payload.update(org_info)
                else:
                    last_stat.raw_payload = org_info
                # Обновляем рейтинг и количество отзывов из org_info
                if org_info.get('rating'):
                    last_stat.rating = org_info.get('rating')
                if org_info.get('reviews_count'):
                    last_stat.reviews_total = org_info.get('reviews_count')

            worker._upsert_stats(db, stats)
            print(f"💾 Сохранено точек статистики: {len(stats)}")

        if posts:
            worker._upsert_posts(db, posts)
            print(f"💾 Сохранено публикаций: {len(posts)}")

        # Сохраняем услуги в UserServices
        if services:
            try:
                cursor = db.conn.cursor()
                cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (business_id,))
                owner_row = cursor.fetchone()
                user_id = owner_row[0] if owner_row else None
                if not user_id:
                    print(f"⚠️ Нет user_id для сохранения услуг")
                else:
                    saved_count = 0
                    updated_count = 0
                    for service in services:
                        try:
                            # Проверяем, что service - это словарь
                            if not isinstance(service, dict):
                                print(f"⚠️ Услуга не является словарём: {type(service)}")
                                continue

                            # Проверяем наличие обязательного поля name
                            if "name" not in service or not service["name"]:
                                print(f"⚠️ Услуга без названия, пропускаем")
                                continue

                            # Проверяем, есть ли уже такая услуга
                            cursor.execute("""
                                SELECT id FROM UserServices
                                WHERE business_id = %s AND name = %s
                                LIMIT 1
                            """, (business_id, service["name"]))
                            existing = cursor.fetchone()

                            # Преобразуем description в строку, если это dict (делаем это один раз в начале)
                            description = service.get("description", "")
                            if isinstance(description, dict):
                                description = description.get("text") or description.get("value") or description.get("content") or str(description)
                            elif not isinstance(description, str):
                                description = str(description) if description else ""

                            # Преобразуем category в строку, если это dict
                            category = service.get("category", "Общие услуги")
                            if isinstance(category, dict):
                                category = category.get("name") or category.get("title") or str(category)
                            elif not isinstance(category, str):
                                category = str(category) if category else "Общие услуги"

                            if not existing:
                                # Добавляем новую услугу
                                service_id = str(uuid.uuid4())
                                cursor.execute("""
                                    INSERT INTO UserServices (id, user_id, business_id, category, name, description, keywords, price, created_at, updated_at)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                """, (
                                    service_id,
                                    user_id,
                                    business_id,
                                    category,
                                    service["name"],
                                    description,
                                    json.dumps(service.get("keywords", [])),
                                    service.get("price", "")
                                ))
                                saved_count += 1
                            else:
                                # Обновляем существующую услугу
                                cursor.execute("""
                                    UPDATE UserServices
                                    SET category = %s, description = %s, keywords = %s, price = %s, updated_at = CURRENT_TIMESTAMP
                                    WHERE business_id = %s AND name = %s
                                """, (
                                    category,
                                    description,
                                    json.dumps(service.get("keywords", [])),
                                    service.get("price", ""),
                                    business_id,
                                        service["name"]
                                    ))
                            updated_count += 1
                        except Exception as e:
                            print(f"⚠️ Ошибка сохранения услуги '{service.get('name', 'unknown')}': {e}")
                            import traceback
                            traceback.print_exc()
                            continue

                    db.conn.commit()
                    print(f"💾 Сохранено услуг: {saved_count} новых, {updated_count} обновлено")
            except Exception as e:
                print(f"❌ Критическая ошибка при сохранении услуг: {e}")
                import traceback
                traceback.print_exc()

            # Обновляем last_sync_at
            cursor = db.conn.cursor()
            cursor.execute("""
                UPDATE externalbusinessaccounts
                SET last_sync_at = CURRENT_TIMESTAMP, last_error = NULL
                WHERE id = %s
            """, (account_id,))

            # Сохраняем срез в cards (Postgres source of truth вместо MapParseResults)
            try:
                cursor.execute("SELECT yandex_url FROM businesses WHERE id = %s", (business_id,))
                raw_url = cursor.fetchone()
                yandex_url = (_row_to_dict(cursor, raw_url) or {}).get("yandex_url") if raw_url else None
                if not yandex_url and external_id:
                    yandex_url = f"https://yandex.ru/sprav/{external_id}"
                url = yandex_url or f"https://yandex.ru/sprav/{external_id or 'unknown'}"
                rating_val = org_info.get('rating') if org_info else None
                reviews_cnt = len(reviews) if reviews else 0
                photos_cnt = org_info.get('photos_count', 0) if org_info else 0
                db.save_new_card_version(
                    business_id,
                    url=url,
                    rating=float(rating_val) if rating_val is not None else None,
                    reviews_count=reviews_cnt,
                    overview=json.dumps({"photos_count": photos_cnt, "posts_count": len(posts) if posts else 0}, ensure_ascii=False),
                )
                db.conn.commit()
                print(f"💾 Сохранена история в cards для business_id={business_id}")
            except Exception as e:
                print(f"⚠️ Ошибка сохранения в cards: {e}")
                import traceback
                traceback.print_exc()

        cursor = db.conn.cursor()
        cursor.execute("UPDATE parsequeue SET status = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (STATUS_COMPLETED, sync_id))
        db.conn.commit()
        db.close()

        print(f"✅ Синхронизация завершена успешно для бизнеса {business_name}")
        return True

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Ошибка при синхронизации бизнеса {business_id}: {e}\n{error_details}")
        try:
            db = DatabaseManager()
            cursor = db.conn.cursor()
            cursor.execute("UPDATE parsequeue SET status = %s, error_message = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s", (STATUS_ERROR, str(e), sync_id))
            cursor.execute("UPDATE externalbusinessaccounts SET last_error = %s WHERE id = %s", (str(e), account_id))
            db.conn.commit()
            db.close()
        except Exception as save_error:
            print(f"⚠️ Не удалось сохранить ошибку в БД: {save_error}")
        return False

@app.route('/api/admin/yandex/sync/status/<string:sync_id>', methods=['GET'])
def admin_sync_status(sync_id):
    """Проверить статус синхронизации"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute("""
            SELECT id, business_id, account_id, source, status, error_message, created_at, updated_at
            FROM parsequeue
            WHERE id = %s AND task_type = 'sync_yandex_business'
        """, (sync_id,))
        raw_sync = cursor.fetchone()
        sync_data = _row_to_dict(cursor, raw_sync) if raw_sync else None

        if not sync_data:
            db.close()
            return jsonify({"error": "Синхронизация не найдена"}), 404

        cursor.execute("SELECT owner_id FROM businesses WHERE id = %s", (sync_data['business_id'],))
        raw_owner = cursor.fetchone()
        owner_row = _row_to_dict(cursor, raw_owner) if raw_owner else None
        owner_id = owner_row.get("owner_id") if owner_row else None

        if owner_id != user_data["user_id"] and not user_data.get("is_superadmin"):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        db.close()

        return jsonify({
            "success": True,
            "sync": {
                "id": sync_data['id'],
                "business_id": sync_data['business_id'],
                "status": sync_data['status'],
                "error_message": sync_data.get('error_message'),
                "created_at": sync_data['created_at'],
                "updated_at": sync_data['updated_at']
            }
        })
    except Exception as e:
        print(f"❌ Ошибка при проверке статуса синхронизации: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/networks', methods=['GET'])
def get_user_networks():
    """Получить список сетей пользователя"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем наличие таблицы networks (Postgres)
        cursor.execute("SELECT to_regclass('public.networks')")
        networks_table_exists = cursor.fetchone()

        if not networks_table_exists:
            db.close()
            return jsonify({
                "success": True,
                "networks": []
            })

        # Получаем сети пользователя
        cursor.execute("""
            SELECT id, name, description
            FROM networks
            WHERE owner_id = %s
            ORDER BY name
        """, (user_data['user_id'],))

        networks = []
        for row in cursor.fetchall():
            row_data = _row_to_dict(cursor, row) if row else {}
            networks.append({
                "id": row_data.get("id"),
                "name": row_data.get("name"),
                "description": row_data.get("description")
            })

        db.close()

        return jsonify({
            "success": True,
            "networks": networks
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка получения сетей: {str(e)}"}), 500

@app.route('/api/networks', methods=['POST'])
def create_network():
    """Создать новую сеть"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json()
        name = data.get('name')
        description = data.get('description', '')

        if not name:
            return jsonify({"error": "Название сети обязательно"}), 400

        db = DatabaseManager()
        network_id = db.create_network(name, user_data['user_id'], description)
        cursor = db.conn.cursor()
        _upsert_network_parent_business(
            cursor=cursor,
            network_id=network_id,
            owner_id=user_data['user_id'],
            network_name=name,
            description=description,
        )
        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "network_id": network_id
        }), 201

    except Exception as e:
        import traceback
        print(f"❌ Ошибка создания сети: {e}")
        print(traceback.format_exc())
        return jsonify({"error": f"Ошибка создания сети: {str(e)}"}), 500

@app.route('/api/networks/<string:network_id>/businesses', methods=['POST'])
def add_business_to_network(network_id):
    """Добавить бизнес в сеть"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json()
        business_id = data.get('business_id')
        name = data.get('name')
        address = data.get('address', '')
        yandex_url = data.get('yandex_url', '')

        if not business_id and not name:
            return jsonify({"error": "Необходимо указать business_id или name"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем права доступа к сети
        cursor.execute("SELECT owner_id FROM networks WHERE id = %s", (network_id,))
        raw_network = cursor.fetchone()
        network = _row_to_dict(cursor, raw_network) if raw_network else None

        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404

        if network.get("owner_id") != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этой сети"}), 403

        # Если business_id указан - добавляем существующий бизнес в сеть
        if business_id:
            # Проверяем, что бизнес принадлежит пользователю
            owner_id = get_business_owner_id(cursor, business_id)
            if not owner_id:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
            if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
                db.close()
                return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

            db.add_business_to_network(business_id, network_id)
            db.close()
            return jsonify({"success": True, "message": "Бизнес добавлен в сеть"})

        # Если business_id не указан - создаем новый бизнес в сети
        if not name:
            db.close()
            return jsonify({"error": "Название бизнеса обязательно"}), 400

        # Создаем новый бизнес
        new_business_id = db.create_business(
            name=name,
            owner_id=user_data['user_id'],
            address=address,
            business_type='beauty_salon',
            yandex_url=yandex_url
        )

        # Добавляем в сеть
        db.add_business_to_network(new_business_id, network_id)

        db.close()

        return jsonify({
            "success": True,
            "business_id": new_business_id,
            "message": "Бизнес создан и добавлен в сеть"
        }), 201

    except Exception as e:
        return jsonify({"error": f"Ошибка добавления бизнеса в сеть: {str(e)}"}), 500

@app.route('/api/auth/register', methods=['POST'])
@rate_limit_if_available("10 per hour")
def register():
    """Регистрация пользователя"""
    try:
        data = request.get_json(silent=True) or {}
        email = normalize_email(data.get('email', ''))
        password = data.get('password', '').strip()
        name = data.get('name', '').strip()
        phone = data.get('phone', '').strip()
        personal_data_consent = bool(data.get('personal_data_consent'))
        consent_version = str(data.get('consent_version') or CONSENT_VERSION).strip()

        if not email or not password:
            return jsonify({"error": "Email и пароль обязательны"}), 400
        if not personal_data_consent:
            return jsonify({"error": "Необходимо согласие на обработку персональных данных"}), 400

        # Создаем пользователя
        from auth_system import create_user
        result = create_user(
            email,
            password,
            name,
            phone,
            personal_data_consent=personal_data_consent,
            consent_version=consent_version,
            consent_ip=request.headers.get('X-Forwarded-For') or request.remote_addr,
            consent_user_agent=request.headers.get('User-Agent'),
            is_verified=False,
        )

        if 'error' in result:
            return jsonify({"error": result['error']}), 400

        email_sent = send_verification_email(
            result['email'],
            result.get('name'),
            result.get('verification_token'),
        )

        return jsonify({
            "success": True,
            "verification_required": True,
            "email_sent": bool(email_sent),
            "message": "Проверьте почту и подтвердите email",
            "user": {
                "id": result['id'],
                "email": result['email'],
                "name": result['name'],
                "phone": result['phone']
            }
        }), 201

    except Exception as e:
        print(f"❌ Ошибка регистрации: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/verify-email', methods=['POST'])
@rate_limit_if_available("20 per hour")
def auth_verify_email():
    """Подтверждение email после регистрации."""
    try:
        data = request.get_json(silent=True) or {}
        token = str(data.get('token') or '').strip()
        if not token:
            return jsonify({"error": "Токен подтверждения обязателен"}), 400

        result = verify_email_token(token)
        if result.get('error'):
            return jsonify({"error": result['error']}), 400

        session_token = create_session(
            str(result['id']),
            ip_address=request.headers.get('X-Forwarded-For') or request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
        )
        if not session_token:
            return jsonify({"error": "Ошибка создания сессии"}), 500

        return jsonify(
            {
                "success": True,
                "token": session_token,
                "user": {
                    "id": result['id'],
                    "email": result['email'],
                    "name": result.get('name'),
                    "phone": result.get('phone'),
                },
            }
        )
    except Exception as e:
        print(f"❌ Ошибка подтверждения email: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/resend-verification', methods=['POST'])
@rate_limit_if_available("5 per hour")
def auth_resend_verification():
    """Повторно отправить письмо подтверждения email."""
    try:
        data = request.get_json(silent=True) or {}
        email = normalize_email(data.get('email', ''))
        if not email:
            return jsonify({"error": "Email обязателен"}), 400

        result = rotate_verification_token(email)
        if result.get('error'):
            return jsonify({"error": result['error']}), 400

        email_sent = send_verification_email(
            result['email'],
            result.get('name'),
            result.get('verification_token'),
        )
        return jsonify(
            {
                "success": True,
                "email_sent": bool(email_sent),
                "message": "Письмо подтверждения отправлено повторно",
            }
        )
    except Exception as e:
        print(f"❌ Ошибка повторной отправки подтверждения: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
@rate_limit_if_available("5 per minute")
def login():
    """Вход пользователя с защитой от brute force атак"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "Неверный формат запроса"}), 400

        email = normalize_email(data.get('email', ''))
        password = data.get('password', '').strip()

        if not email or not password:
            return jsonify({"error": "Email и пароль обязательны"}), 400

        # Аутентификация
        result = authenticate_user(email, password)

        if 'error' in result:
            if result.get('error') == 'account_blocked':
                return jsonify({"error": "account_blocked", "message": "user is blocked"}), 403
            return jsonify({"error": result['error']}), 401

        # Проверяем, есть ли у пользователя хотя бы один активный бизнес
        # Если все бизнесы заблокированы, пользователь не может войти
        db = None
        try:
            db = DatabaseManager()
            is_superadmin = db.is_superadmin(result['id'])

            if not is_superadmin:
                # Проверяем активные бизнесы для обычных пользователей
                businesses = db.get_businesses_by_owner(result['id'])
                if len(businesses) == 0:
                    if db:
                        db.close()
                    return jsonify({"error": "Все ваши бизнесы заблокированы. Обратитесь к администратору."}), 403
        except Exception as db_error:
            print(f"❌ Ошибка проверки бизнесов: {db_error}")
            import traceback
            traceback.print_exc()
            if db:
                db.close()
            return jsonify({"error": "Ошибка проверки данных пользователя"}), 500
        finally:
            if db:
                db.close()

        # Создаем сессию
        try:
            session_token = create_session(result['id'])
            if not session_token:
                return jsonify({"error": "Ошибка создания сессии"}), 500
        except Exception as session_error:
            logger.warning("Login session creation failed: %s", type(session_error).__name__)
            return jsonify({"error": "Ошибка создания сессии"}), 500

        return jsonify({
            "success": True,
            "user": {
                "id": result['id'],
                "email": result.get('email', ''),
                "name": result.get('name', ''),
                "phone": result.get('phone', '')
            },
            "token": session_token
        })

    except Exception as e:
        logger.warning("Login endpoint failed: %s", type(e).__name__)
        payload = {"error": "Ошибка входа"}
        if app.debug:
            payload["details"] = str(e)
        return jsonify(payload), 500

@app.route('/api/admin/proxies', methods=['GET'])
def get_proxies():
    """Получить список прокси (только для суперадмина)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403

        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT id, proxy_type, host, port, is_active, is_working,
                   success_count, failure_count, last_used_at, last_checked_at
            FROM ProxyServers
            ORDER BY created_at DESC
        """)

        proxies = []
        for row in cursor.fetchall():
            row_get = row.get if hasattr(row, "get") else None
            proxies.append({
                "id": (row_get("id") if row_get else row[0]),
                "type": (row_get("proxy_type") if row_get else row[1]),
                "host": (row_get("host") if row_get else row[2]),
                "port": (row_get("port") if row_get else row[3]),
                "is_active": bool(row_get("is_active") if row_get else row[4]),
                "is_working": bool(row_get("is_working") if row_get else row[5]),
                "success_count": (row_get("success_count") if row_get else row[6]),
                "failure_count": (row_get("failure_count") if row_get else row[7]),
                "last_used_at": (row_get("last_used_at") if row_get else row[8]),
                "last_checked_at": (row_get("last_checked_at") if row_get else row[9]),
            })

        db.close()
        return jsonify({"proxies": proxies})

    except Exception as e:
        print(f"❌ Ошибка получения прокси: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/proxies', methods=['POST'])
def add_proxy():
    """Добавить прокси (только для суперадмина)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403

        data = request.json
        proxy_id = str(uuid.uuid4())

        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO ProxyServers (
                id, proxy_type, host, port, username, password,
                is_active, is_working, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, TRUE, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            proxy_id,
            data.get('type', 'http'),
            data['host'],
            data['port'],
            data.get('username'),
            data.get('password')  # TODO: зашифровать
        ))
        db.conn.commit()
        db.close()

        return jsonify({"success": True, "proxy_id": proxy_id})

    except Exception as e:
        print(f"❌ Ошибка добавления прокси: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/proxies/<proxy_id>', methods=['DELETE'])
def delete_proxy(proxy_id):
    """Удалить прокси (только для суперадмина)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403

        cursor = db.conn.cursor()
        cursor.execute("DELETE FROM ProxyServers WHERE id = %s", (proxy_id,))
        db.conn.commit()
        db.close()

        return jsonify({"success": True})

    except Exception as e:
        print(f"❌ Ошибка удаления прокси: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/proxies/<proxy_id>/toggle', methods=['POST'])
def toggle_proxy(proxy_id):
    """Включить/выключить прокси (только для суперадмина)"""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403

        cursor = db.conn.cursor()
        # Получаем текущий статус
        cursor.execute("SELECT is_active FROM ProxyServers WHERE id = %s", (proxy_id,))
        row = cursor.fetchone()
        if not row:
            db.close()
            return jsonify({"error": "Прокси не найден"}), 404

        current_status = row.get("is_active") if hasattr(row, "get") else row[0]
        new_status = False if bool(current_status) else True
        cursor.execute("""
            UPDATE ProxyServers
            SET is_active = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (new_status, proxy_id))
        db.conn.commit()
        db.close()

        return jsonify({"success": True, "is_active": bool(new_status)})

    except Exception as e:
        print(f"❌ Ошибка переключения прокси: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/prompts', methods=['GET', 'OPTIONS'])
def get_prompts():
    """Получить все промпты (только для суперадмина)"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            return jsonify({"error": "Недостаточно прав"}), 403

        cursor = db.conn.cursor()
        # Проверяем, существует ли таблица, если нет - создаём
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS aiprompts (
                id TEXT PRIMARY KEY,
                prompt_type TEXT UNIQUE NOT NULL,
                prompt_text TEXT NOT NULL,
                description TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT,
                FOREIGN KEY (updated_by) REFERENCES Users(id) ON DELETE SET NULL
            )
        """)
        db.conn.commit()

        default_prompts = get_default_ai_prompts()
        for prompt_type, prompt_text, description in default_prompts:
            cursor.execute(
                """
                INSERT INTO aiprompts (id, prompt_type, prompt_text, description)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (prompt_type) DO NOTHING
                """,
                (f"prompt_{prompt_type}", prompt_type, prompt_text, description),
            )

        db.conn.commit()
        cursor.execute("SELECT prompt_type, prompt_text, description, updated_at, updated_by FROM aiprompts ORDER BY prompt_type")
        rows = cursor.fetchall()

        prompts = []
        for row in rows:
            row_data = _row_to_dict(cursor, row) if row else {}
            prompts.append({
                'type': row_data.get('prompt_type'),
                'text': row_data.get('prompt_text'),
                'description': row_data.get('description'),
                'updated_at': row_data.get('updated_at'),
                'updated_by': row_data.get('updated_by')
            })

        db.close()
        return jsonify({"prompts": prompts})

    except Exception as e:
        print(f"❌ Ошибка получения промптов: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
