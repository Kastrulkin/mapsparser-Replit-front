from legacy_routes import shared as _shared

globals().update(_shared.runtime_namespace)

@app.route('/api/services/update/<string:service_id>', methods=['PUT', 'OPTIONS'])
def update_service(service_id):
    """Обновление существующей услуги пользователя."""
    try:
        print(f"🔍 Начало обновления услуги: {service_id}", flush=True)
        if request.method == 'OPTIONS':
            return ('', 204)

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "Данные не предоставлены"}), 400

        print(f"🔍 DEBUG update_service: data keys = {list(data.keys())}", flush=True)

        category = data.get('category', '')
        name = data.get('name', '')
        description = data.get('description', '')
        optimized_description = data.get('optimized_description', '')  # Новое поле для SEO описания
        keywords = data.get('keywords', [])
        price = data.get('price', '')
        user_id = user_data['user_id']

        print(f"🔍 DEBUG update_service: keywords type = {type(keywords)}, value = {keywords}", flush=True)

        # Преобразуем keywords в строку JSON, если это массив
        if isinstance(keywords, list):
            keywords_str = json.dumps(keywords, ensure_ascii=False)
        elif isinstance(keywords, str):
            keywords_str = keywords
        else:
            keywords_str = json.dumps([])

        print(f"🔍 DEBUG update_service: keywords_str = {keywords_str[:100]}", flush=True)

        if not name:
            return jsonify({"error": "Название услуги обязательно"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем, есть ли поля optimized_description и optimized_name в таблице
        columns = _table_columns(cursor, "userservices")
        has_optimized_description = 'optimized_description' in columns
        has_optimized_name = 'optimized_name' in columns

        optimized_name = data.get('optimized_name', '')

        print(f"🔍 DEBUG update_service: has_optimized_description = {has_optimized_description}, has_optimized_name = {has_optimized_name}", flush=True)
        print(f"🔍 DEBUG update_service: columns = {columns}", flush=True)
        print(f"🔍 DEBUG update_service: optimized_name = '{optimized_name}' (type: {type(optimized_name)}, length: {len(optimized_name) if optimized_name else 0})", flush=True)
        print(f"🔍 DEBUG update_service: optimized_description = '{optimized_description[:100] if optimized_description else ''}...' (type: {type(optimized_description)}, length: {len(optimized_description) if optimized_description else 0})", flush=True)

        cursor.execute(
            """
            SELECT name, description, optimized_name, optimized_description, business_id
            FROM userservices
            WHERE id = %s AND user_id = %s
            LIMIT 1
            """,
            (service_id, user_id),
        )
        previous_row = cursor.fetchone()
        if not previous_row:
            db.close()
            return jsonify({"error": "Услуга не найдена или нет прав для редактирования"}), 404

        previous_data = _row_to_dict(cursor, previous_row) or {}

        if has_optimized_description and has_optimized_name:
            print(f"🔍 DEBUG update_service: Обновление с optimized_description и optimized_name", flush=True)
            cursor.execute(
                """
                UPDATE userservices SET
                category = %s, name = %s, optimized_name = %s, description = %s,
                optimized_description = %s, keywords = %s, price = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
                """,
                (category, name, optimized_name, description, optimized_description, keywords_str, price, service_id, user_id),
            )
            print(f"✅ DEBUG update_service: UPDATE выполнен, rowcount = {cursor.rowcount}", flush=True)

        else:
            print(f"🔍 DEBUG update_service: Обновление БЕЗ optimized_description/name", flush=True)
            cursor.execute(
                """
                UPDATE userservices SET
                category = %s, name = %s, description = %s, keywords = %s, price = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND user_id = %s
                """,
                (category, name, description, keywords_str, price, service_id, user_id),
            )

        if cursor.rowcount == 0:
            db.close()
            return jsonify({"error": "Услуга не найдена или нет прав для редактирования"}), 404

        db.conn.commit()
        db.close()

        request_business_id = _resolve_request_business_id(user_data, json_data=data)
        service_business_id = str(previous_data.get("business_id") or "").strip() or None
        business_id = request_business_id or service_business_id
        prev_name = str(previous_data.get("name") or "")
        prev_description = str(previous_data.get("description") or "")
        prev_optimized_name = str(previous_data.get("optimized_name") or "")
        prev_optimized_description = str(previous_data.get("optimized_description") or "")
        next_name = str(name or "")
        next_description = str(description or "")
        next_optimized_name = str(optimized_name or "")
        next_optimized_description = str(optimized_description or "")

        if prev_optimized_name and not next_optimized_name:
            accepted_name = _normalize_text_for_semantic_compare(next_name) != _normalize_text_for_semantic_compare(prev_name)
            if accepted_name:
                edited_before_accept = _normalize_text_for_semantic_compare(next_name) != _normalize_text_for_semantic_compare(prev_optimized_name)
                record_ai_learning_event(
                    capability="services.optimize",
                    event_type="accepted",
                    intent="operations",
                    user_id=user_id,
                    business_id=business_id,
                    accepted=True,
                    edited_before_accept=edited_before_accept,
                    prompt_key="service_optimization",
                    prompt_version="v1",
                    draft_text=prev_optimized_name,
                    final_text=next_name,
                    metadata={"field": "name", "service_id": service_id},
                )
            else:
                record_ai_learning_event(
                    capability="services.optimize",
                    event_type="rejected",
                    intent="operations",
                    user_id=user_id,
                    business_id=business_id,
                    rejected=True,
                    prompt_key="service_optimization",
                    prompt_version="v1",
                    draft_text=prev_optimized_name,
                    final_text=prev_name,
                    metadata={"field": "name", "service_id": service_id},
                )

        if prev_optimized_description and not next_optimized_description:
            accepted_description = _normalize_text_for_semantic_compare(next_description) != _normalize_text_for_semantic_compare(prev_description)
            if accepted_description:
                edited_before_accept = _normalize_text_for_semantic_compare(next_description) != _normalize_text_for_semantic_compare(prev_optimized_description)
                record_ai_learning_event(
                    capability="services.optimize",
                    event_type="accepted",
                    intent="operations",
                    user_id=user_id,
                    business_id=business_id,
                    accepted=True,
                    edited_before_accept=edited_before_accept,
                    prompt_key="service_optimization",
                    prompt_version="v1",
                    draft_text=prev_optimized_description,
                    final_text=next_description,
                    metadata={"field": "description", "service_id": service_id},
                )
            else:
                record_ai_learning_event(
                    capability="services.optimize",
                    event_type="rejected",
                    intent="operations",
                    user_id=user_id,
                    business_id=business_id,
                    rejected=True,
                    prompt_key="service_optimization",
                    prompt_version="v1",
                    draft_text=prev_optimized_description,
                    final_text=prev_description,
                    metadata={"field": "description", "service_id": service_id},
                )

        return jsonify({"success": True, "message": "Услуга обновлена"})

    except Exception as e:
        print(f"❌ Ошибка обновления услуги: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/services/delete/<string:service_id>', methods=['DELETE', 'OPTIONS'])
def delete_service(service_id):
    """Удаление услуги пользователя."""
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

        user_id = user_data['user_id']

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("DELETE FROM userservices WHERE id = %s AND user_id = %s", (service_id, user_id))

        if cursor.rowcount == 0:
            db.close()
            return jsonify({"error": "Услуга не найдена или нет прав для удаления"}), 404

        db.conn.commit()
        db.close()
        return jsonify({"success": True, "message": "Услуга удалена"})

    except Exception as e:
        print(f"❌ Ошибка удаления услуги: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/client-info', methods=['GET', 'POST', 'PUT', 'OPTIONS'])
def client_info():
    try:
        # Preflight
        if request.method == 'OPTIONS':
            return ('', 204)

        # Авторизация
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        user_id = user_data.get('user_id') or user_data.get('id')
        print(f"🔍 /api/client-info: method={request.method}, user_id={user_id}")

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Postgres-only: данные профиля из businesses, userservices, businessprofiles, users;
        # ссылки на карты — только из businessmaplinks. Таблица ClientInfo не используется.

        if request.method == 'GET':
            current_business_id = request.args.get('business_id')
            print(f"🔍 GET /api/client-info: method=GET, business_id={current_business_id}, user_id={user_id}")

            # Если передан business_id — данные только из таблицы businesses (lowercase). Фильтр is_active согласован с dropdown (auth/me).
            if current_business_id:
                print(f"🔍 GET /api/client-info: Ищу бизнес в таблице businesses, business_id={current_business_id}")
                cursor.execute(
                    "SELECT owner_id, name, business_type, address, working_hours, is_active, city, geo_lat, geo_lon, site, website FROM businesses WHERE id = %s AND (is_active = TRUE OR is_active IS NULL)",
                    (current_business_id,),
                )
                business_row = cursor.fetchone()
                row_dict = _row_to_dict(cursor, business_row)

                if row_dict:
                    owner_id = row_dict.get("owner_id")
                    business_name, business_type, address, working_hours = _business_display_fields(row_dict)
                    is_active_val = row_dict.get("is_active")
                    city = (row_dict.get("city") or "").strip() or None
                    geo_lat = row_dict.get("geo_lat")
                    geo_lon = row_dict.get("geo_lon")
                    website = str(row_dict.get("site") or row_dict.get("website") or "").strip()
                    city_suggestion = None
                    if not city and address:
                        city_suggestion = suggest_city_from_address(address)
                    print(f"🔍 GET /api/client-info: Бизнес найден, owner_id={owner_id}, name={business_name!r}, is_active={is_active_val}")
                    if owner_id == user_id or user_data.get("is_superadmin"):
                        print(f"✅ GET /api/client-info: Доступ разрешен, возвращаю данные из businesses")
                        links = []
                        cursor.execute("""
                            SELECT id, url, map_type, created_at
                            FROM businessmaplinks
                            WHERE business_id = %s
                            ORDER BY created_at DESC
                        """, (current_business_id,))
                        link_rows = cursor.fetchall()
                        for r in link_rows:
                            rd = _row_to_dict(cursor, r) if not hasattr(r, "keys") else dict(r)
                            if rd:
                                links.append({
                                    "id": rd.get("id"),
                                    "url": rd.get("url") or "",
                                    "mapType": rd.get("map_type") or "other",
                                    "createdAt": rd.get("created_at"),
                                })

                        cursor.execute("""
                            SELECT name, description, category, price
                            FROM userservices
                            WHERE business_id = %s
                            ORDER BY created_at DESC
                        """, (current_business_id,))
                        services_rows = cursor.fetchall()
                        services_list = []
                        for r in services_rows:
                            rd = _row_to_dict(cursor, r) if not hasattr(r, "keys") else dict(r)
                            if rd:
                                services_list.append({
                                    "name": rd.get("name") or "",
                                    "description": rd.get("description") or "",
                                    "category": rd.get("category") or "",
                                    "price": rd.get("price") or "",
                                })

                        owner_data = None
                        cursor.execute("SELECT contact_name, contact_phone, contact_email FROM businessprofiles WHERE business_id = %s", (current_business_id,))
                        profile_row = cursor.fetchone()
                        if profile_row:
                            pr = _row_to_dict(cursor, profile_row)
                            if pr and (pr.get("contact_name") or pr.get("contact_phone") or pr.get("contact_email")):
                                owner_data = {
                                    "id": owner_id,
                                    "name": (pr.get("contact_name") or "").strip(),
                                    "phone": (pr.get("contact_phone") or "").strip(),
                                    "email": (pr.get("contact_email") or "").strip(),
                                }
                        if not owner_data and owner_id:
                            cursor.execute("SELECT id, email, name, phone FROM users WHERE id = %s", (owner_id,))
                            owner_row = cursor.fetchone()
                            if owner_row:
                                ur = _row_to_dict(cursor, owner_row)
                                if ur:
                                    owner_data = {
                                        "id": ur.get("id"),
                                        "email": ur.get("email") or "",
                                        "name": ur.get("name") or "",
                                        "phone": ur.get("phone") or "",
                                    }

                        payload = {
                            "success": True,
                            "businessName": business_name or "",
                            "businessType": business_type or "",
                            "address": address or "",
                            "workingHours": working_hours or "",
                            "city": city or "",
                            "citySuggestion": city_suggestion or "",
                            "geoLat": geo_lat,
                            "geoLon": geo_lon,
                            "website": website,
                            "site": website,
                            "description": "",
                            "services": services_list,
                            "mapLinks": links,
                            "owner": owner_data,
                        }
                        if getattr(app, "debug", False):
                            payload["_debug"] = {
                                "foundBusiness": True,
                                "isActive": is_active_val,
                                "returnedName": business_name or "",
                            }
                        db.close()
                        return jsonify(payload)
                    else:
                        print(f"❌ GET /api/client-info: Нет доступа к бизнесу, owner_id={owner_id}, user_id={user_id}")
                        db.close()
                        return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
                else:
                    print(f"⚠️ GET /api/client-info: Бизнес не найден, business_id={current_business_id}")
                    err_payload = {"error": "Бизнес не найден"}
                    if getattr(app, "debug", False):
                        err_payload["_debug"] = {"foundBusiness": False, "isActive": None, "returnedName": ""}
                    db.close()
                    return jsonify(err_payload), 404

            # business_id не передан — первый бизнес пользователя (фильтр is_active как в dropdown)
            cursor.execute(
                "SELECT id FROM businesses WHERE owner_id = %s AND (is_active = TRUE OR is_active IS NULL) ORDER BY created_at ASC LIMIT 1",
                (user_id,),
            )
            first_row = cursor.fetchone()
            if not first_row:
                db.close()
                return jsonify({
                    "success": True,
                    "businessName": "",
                    "businessType": "",
                    "address": "",
                    "workingHours": "",
                    "description": "",
                    "website": "",
                    "site": "",
                    "services": [],
                    "mapLinks": [],
                    "owner": None
                })
            first_dict = _row_to_dict(cursor, first_row)
            current_business_id = first_dict.get("id") if first_dict else None
            if not current_business_id:
                db.close()
                return jsonify({"success": True, "businessName": "", "businessType": "", "address": "", "workingHours": "", "description": "", "website": "", "site": "", "services": [], "mapLinks": [], "owner": None})
            cursor.execute(
                "SELECT owner_id, name, business_type, address, working_hours, is_active, city, geo_lat, geo_lon, site, website FROM businesses WHERE id = %s AND (is_active = TRUE OR is_active IS NULL)",
                (current_business_id,),
            )
            business_row = cursor.fetchone()
            row_dict = _row_to_dict(cursor, business_row)
            if not row_dict:
                db.close()
                return jsonify({"success": True, "businessName": "", "businessType": "", "address": "", "workingHours": "", "city": "", "citySuggestion": "", "geoLat": None, "geoLon": None, "description": "", "website": "", "site": "", "services": [], "mapLinks": [], "owner": None})
            owner_id = row_dict.get("owner_id")
            business_name, business_type, address, working_hours = _business_display_fields(row_dict)
            is_active_val = row_dict.get("is_active")
            city = (row_dict.get("city") or "").strip() or None
            geo_lat, geo_lon = row_dict.get("geo_lat"), row_dict.get("geo_lon")
            website = str(row_dict.get("site") or row_dict.get("website") or "").strip()
            city_suggestion = suggest_city_from_address(address) if not city and address else None
            links = []
            cursor.execute("""
                SELECT id, url, map_type, created_at FROM businessmaplinks WHERE business_id = %s ORDER BY created_at DESC
            """, (current_business_id,))
            for r in cursor.fetchall():
                rd = _row_to_dict(cursor, r) if not hasattr(r, "keys") else dict(r)
                if rd:
                    links.append({
                        "id": rd.get("id"),
                        "url": rd.get("url") or "",
                        "mapType": rd.get("map_type") or "other",
                        "createdAt": rd.get("created_at"),
                    })
            cursor.execute("SELECT name, description, category, price FROM userservices WHERE business_id = %s ORDER BY created_at DESC", (current_business_id,))
            services_list = []
            for r in cursor.fetchall():
                rd = _row_to_dict(cursor, r) if not hasattr(r, "keys") else dict(r)
                if rd:
                    services_list.append({
                        "name": rd.get("name") or "",
                        "description": rd.get("description") or "",
                        "category": rd.get("category") or "",
                        "price": rd.get("price") or "",
                    })
            owner_data = None
            cursor.execute("SELECT contact_name, contact_phone, contact_email FROM businessprofiles WHERE business_id = %s", (current_business_id,))
            profile_row = cursor.fetchone()
            if profile_row:
                pr = _row_to_dict(cursor, profile_row)
                if pr and (pr.get("contact_name") or pr.get("contact_phone") or pr.get("contact_email")):
                    owner_data = {"id": owner_id, "name": (pr.get("contact_name") or "").strip(), "phone": (pr.get("contact_phone") or "").strip(), "email": (pr.get("contact_email") or "").strip()}
            if not owner_data and owner_id:
                cursor.execute("SELECT id, email, name, phone FROM users WHERE id = %s", (owner_id,))
                owner_row = cursor.fetchone()
                if owner_row:
                    ur = _row_to_dict(cursor, owner_row)
                    if ur:
                        owner_data = {"id": ur.get("id"), "email": ur.get("email") or "", "name": ur.get("name") or "", "phone": ur.get("phone") or ""}
            payload = {
                "success": True,
                "businessName": business_name or "",
                "businessType": business_type or "",
                "address": address or "",
                "workingHours": working_hours or "",
                "city": city or "",
                "citySuggestion": city_suggestion or "",
                "geoLat": geo_lat,
                "geoLon": geo_lon,
                "website": website,
                "site": website,
                "description": "",
                "services": services_list,
                "mapLinks": links,
                "owner": owner_data,
            }
            if getattr(app, "debug", False):
                payload["_debug"] = {"foundBusiness": True, "isActive": is_active_val, "returnedName": business_name or ""}
            db.close()
            return jsonify(payload)

        # POST/PUT: сохранить/обновить
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400

        # Получаем business_id из запроса или используем первый бизнес пользователя
        business_id = request.args.get('business_id') or data.get('business_id') or data.get('businessId')
        print(f"📝 POST /api/client-info: business_id={business_id}, data keys={list(data.keys()) if data else 'None'}")
        if not business_id:
            # Если business_id не передан, пытаемся найти первый бизнес пользователя
            cursor.execute("SELECT id FROM businesses WHERE owner_id = %s AND is_active = TRUE LIMIT 1", (user_id,))
            business_row = cursor.fetchone()
            if business_row:
                business_id = business_row[0] if isinstance(business_row, tuple) else business_row['id']
            else:
                # Если бизнеса нет, используем user_id как business_id для обратной совместимости
                business_id = user_id

        # Сохраняем ссылки на карты в businessmaplinks (Postgres-only, ClientInfo не используется)
        map_links = None
        if 'mapLinks' in data:
            map_links = data.get('mapLinks')
        elif 'map_links' in data:
            map_links = data.get('map_links')
        # Не перезаписывать business_id: он уже задан выше из args/data/БД

        print(f"🔍 DEBUG client-info: business_id={business_id}, map_links={map_links}, type={type(map_links)}")

        def detect_map_type(url: str) -> str:
            u = (url or '').lower()
            if 'yandex' in u:
                return 'yandex'
            if '2gis' in u:
                return '2gis'
            if is_google_map_url(u):
                return 'google'
            if 'maps.apple.com' in u:
                return 'apple'
            return 'other'

        # Парсер больше не запускается автоматически при сохранении ссылок
        # Он запускается только вручную через кнопку "Запустить парсер" на странице "Обзор карточки"

        # mapLinks: обновляем только если в теле явно передан ключ mapLinks/map_links. Если ключа нет — существующие ссылки не трогаем. Пустой список [] = удалить все.
        if business_id and ("mapLinks" in data or "map_links" in data) and isinstance(map_links, list):
            print(f"📝 SAVE mapLinks: business_id={business_id}, user_id={user_id}, map_links={map_links}")
            valid_links = []
            for link in map_links:
                url = link.get('url') if isinstance(link, dict) else str(link)
                if url and url.strip():
                    normalized_url = normalize_map_url(url.strip())
                    if normalized_url:
                        valid_links.append(normalized_url)
            print(f"📝 SAVE mapLinks: valid_links={valid_links}, count={len(valid_links)}")

            cursor.execute("DELETE FROM businessmaplinks WHERE business_id = %s", (business_id,))
            deleted_count = cursor.rowcount
            print(f"📝 DELETE mapLinks: business_id={business_id}, deleted_count={deleted_count}")

            inserted_count = 0
            for url in valid_links:
                map_type = detect_map_type(url)
                link_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO businessmaplinks (id, user_id, business_id, url, map_type, created_at)
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (link_id, user_id, business_id, url, map_type))
                inserted_count += cursor.rowcount
                print(f"📝 INSERT mapLink: id={link_id}, business_id={business_id}, url={url}, map_type={map_type}")

            db.conn.commit()
            print(f"📝 mapLinks: commit() выполнен (DELETE + {inserted_count} INSERT)")

            # Парсим ll=lon,lat из первой ссылки на Яндекс.Карты и сохраняем в businesses
            for url in valid_links:
                if "yandex" in (url or "").lower() and "ll=" in (url or ""):
                    geo_lon, geo_lat = parse_ll_from_maps_url(url)
                    if geo_lon is not None and geo_lat is not None:
                        cursor.execute(
                            "UPDATE businesses SET geo_lon = %s, geo_lat = %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
                            (geo_lon, geo_lat, business_id),
                        )
                        db.conn.commit()
                        print(f"📝 geo: business_id={business_id} geo_lon={geo_lon} geo_lat={geo_lat} из ll в ссылке")
                    break

            cursor.execute("SELECT COUNT(*) FROM businessmaplinks WHERE business_id = %s", (business_id,))
            count_row = cursor.fetchone()
            saved_count = count_row['count'] if isinstance(count_row, dict) else count_row[0]
            print(f"📝 VERIFY mapLinks: business_id={business_id}, saved_count={saved_count}")

        # Всегда возвращаем текущие ссылки для бизнеса
        current_links = []
        if business_id:
            print(f"📖 GET mapLinks: business_id={business_id}")
            cursor.execute("""
                SELECT id, url, map_type, created_at
                FROM businessmaplinks
                WHERE business_id = %s
                ORDER BY created_at DESC
            """, (business_id,))
            link_rows = cursor.fetchall()
            current_links = [
                {
                    "id": r['id'] if isinstance(r, dict) else r[0],
                    "url": r['url'] if isinstance(r, dict) else r[1],
                    "mapType": r['map_type'] if isinstance(r, dict) else r[2],
                    "createdAt": r['created_at'] if isinstance(r, dict) else r[3]
                } for r in link_rows
            ]
            print(f"📖 GET mapLinks: business_id={business_id}, found_count={len(current_links)}, links={[l['url'] for l in current_links]}")

        def _looks_like_url(value: Any) -> bool:
            text = str(value or "").strip().lower()
            if not text:
                return False
            return (
                "://" in text
                or text.startswith("www.")
                or "maps.app.goo.gl" in text
                or "yandex." in text
                or "2gis." in text
                or is_google_map_url(text)
                or "maps.apple.com" in text
            )

        # Синхронизация с Businesses: обновляем существующий бизнес
        try:
            business_name = data.get('businessName') or ''

            # Если business_id не передан, ищем существующий бизнес пользователя
            if not business_id:
                # Сначала ищем по имени (если переименовали)
                if business_name:
                    cursor.execute("""
                        SELECT id FROM businesses
                        WHERE owner_id = %s AND name = %s AND is_active = TRUE
                        LIMIT 1
                    """, (user_id, business_name))
                    existing_by_name = cursor.fetchone()
                    if existing_by_name:
                        business_id = existing_by_name['id'] if isinstance(existing_by_name, dict) else existing_by_name[0]
                        print(f"✅ Найден бизнес по имени: {business_name} (ID: {business_id})")

                # Если не нашли по имени, берём первый активный бизнес пользователя
                if not business_id:
                    cursor.execute("""
                        SELECT id FROM businesses
                        WHERE owner_id = %s AND is_active = TRUE
                        ORDER BY created_at ASC
                        LIMIT 1
                    """, (user_id,))
                    first_business = cursor.fetchone()
                    if first_business:
                        business_id = first_business['id'] if isinstance(first_business, dict) else first_business[0]
                        print(f"✅ Используется первый бизнес пользователя (ID: {business_id})")

            # Обновляем бизнес, если найден
            if business_id:
                # Проверяем доступ
                owner_id = get_business_owner_id(cursor, business_id)
                if not owner_id or (owner_id != user_id and not user_data.get('is_superadmin')):
                    print(f"⚠️ Нет доступа к бизнесу {business_id}")
                    business_id = None
                else:
                    address_value = data.get('address')
                    city_value = data.get('city') if 'city' in data else None
                    if address_value is not None and _looks_like_url(address_value):
                        raise ValueError("Поле «Адрес» не должно содержать ссылку. Добавьте ссылку в блок «Ссылки на карты».")
                    if city_value is not None and _looks_like_url(city_value):
                        raise ValueError("Поле «Город» не должно содержать ссылку. Добавьте ссылку в блок «Ссылки на карты».")

                    # Обновляем данные бизнеса
                    updates = []
                    params = []
                    website_value = data.get('website') if 'website' in data else data.get('site') if 'site' in data else None
                    if data.get('businessName') is not None:
                        updates.append('name = %s'); params.append(data.get('businessName'))
                    if data.get('address') is not None:
                        updates.append('address = %s'); params.append(data.get('address'))
                    if data.get('workingHours') is not None:
                        updates.append('working_hours = %s'); params.append(data.get('workingHours'))
                    if website_value is not None:
                        normalized_website = str(website_value or "").strip()
                        updates.append('site = %s'); params.append(normalized_website or None)
                        updates.append('website = %s'); params.append(normalized_website or None)
                    if data.get('businessType') is not None:
                        business_type_value = data.get('businessType')
                        print(f"📋 Сохраняем businessType в businesses: {business_type_value}")
                        updates.append('business_type = %s'); params.append(business_type_value)
                    # city: ручной приоритет; если не передан и в БД пусто — подсказка из address
                    if 'city' in data:
                        updates.append('city = %s'); params.append((data.get('city') or "").strip() or None)
                    else:
                        cursor.execute("SELECT city, address FROM businesses WHERE id = %s", (business_id,))
                        cur_row = cursor.fetchone()
                        cur_dict = _row_to_dict(cursor, cur_row) if cur_row else {}
                        current_city = (cur_dict.get("city") or "").strip() if cur_dict else ""
                        if not current_city:
                            addr = data.get('address') or (cur_dict.get("address") or "")
                            suggested = suggest_city_from_address(addr)
                            if suggested:
                                updates.append('city = %s'); params.append(suggested)
                    if updates:
                        updates.append('updated_at = CURRENT_TIMESTAMP')
                        params.append(business_id)
                        cursor.execute(f"UPDATE businesses SET {', '.join(updates)} WHERE id = %s", params)
                        db.conn.commit()
                        print(f"✅ Обновлён бизнес: {business_id}")
        except Exception as e:
            print(f"⚠️ Ошибка синхронизации с Businesses: {e}")
            import traceback
            traceback.print_exc()

        # Возвращаем полные данные бизнеса после сохранения
        response_data = {
            "success": True,
            "mapLinks": current_links
        }

        # Ответ: данные бизнеса всегда из таблицы businesses (lowercase), маппинг через cursor.description
        if business_id:
            cursor.execute("SELECT name, business_type, address, working_hours, city, geo_lat, geo_lon, site, website FROM businesses WHERE id = %s", (business_id,))
            business_row = cursor.fetchone()
            row_dict = _row_to_dict(cursor, business_row)
            if row_dict:
                business_name, business_type, address, working_hours = _business_display_fields(row_dict)
                city = (row_dict.get("city") or "").strip() or ""
                city_suggestion = suggest_city_from_address(address) if not city and address else ""
                website = str(row_dict.get("site") or row_dict.get("website") or "").strip()
                print(f"📋 POST /api/client-info: из businesses для business_id={business_id}: name={business_name!r}, businessType={business_type!r}")
                response_data.update({
                    "businessName": business_name or "",
                    "businessType": business_type or "",
                    "address": address or "",
                    "workingHours": working_hours or "",
                    "city": city or "",
                    "citySuggestion": city_suggestion or "",
                    "geoLat": row_dict.get("geo_lat"),
                    "geoLon": row_dict.get("geo_lon"),
                    "website": website,
                    "site": website,
                })

        db.close()
        return jsonify(response_data)

    except Exception as e:
        import traceback
        print(f"❌ Ошибка в /api/client-info: {e}")
        print(f"❌ Method: {request.method}")
        print(f"❌ User ID: {user_id if 'user_id' in locals() else 'N/A'}")
        try:
            if request.method == 'POST' or request.method == 'PUT':
                print(f"❌ Request JSON: {request.json}")
                print(f"❌ Request data: {request.get_data(as_text=True)[:500]}")
            elif request.method == 'GET':
                print(f"❌ Request args: {request.args}")
        except Exception as log_err:
            print(f"❌ Ошибка логирования request: {log_err}")
        print("❌ Traceback:")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/business/<string:business_id>/parse-status', methods=['GET'])
def get_parse_status(business_id):
    """Получить статус парсинга для бизнеса из очереди"""
    try:
        parse_refresh_cooldown_days = 7

        def _coerce_parse_datetime(raw_value: Any) -> Optional[datetime]:
            if raw_value is None:
                return None
            if isinstance(raw_value, datetime):
                parsed_dt = raw_value
            else:
                raw_text = str(raw_value).strip()
                if not raw_text:
                    return None
                normalized_text = raw_text.replace("Z", "+00:00")
                try:
                    parsed_dt = datetime.fromisoformat(normalized_text)
                except ValueError:
                    return None

            if parsed_dt.tzinfo is not None:
                try:
                    return parsed_dt.astimezone().replace(tzinfo=None)
                except Exception:
                    return parsed_dt.replace(tzinfo=None)
            return parsed_dt

        def _serialize_parse_datetime(raw_value: Any) -> Optional[str]:
            parsed_dt = _coerce_parse_datetime(raw_value)
            if not parsed_dt:
                return None
            return parsed_dt.replace(microsecond=0).isoformat()

        def _build_parse_refresh_policy(cursor: Any, business_id_value: str, owner_id_value: Optional[str]) -> Dict[str, Any]:
            cursor.execute("SELECT to_regclass('public.invites') AS invites_table")
            raw_invites_table = cursor.fetchone()
            invites_table_row = _row_to_dict(cursor, raw_invites_table) if raw_invites_table else None
            invites_table_exists = bool((invites_table_row or {}).get("invites_table"))

            active_statuses = ["pending", "queued", "processing", "captcha"]
            cursor.execute(
                """
                SELECT status, created_at
                FROM parsequeue
                WHERE business_id = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (business_id_value,),
            )
            raw_latest_queue = cursor.fetchone()
            latest_queue = _row_to_dict(cursor, raw_latest_queue) if raw_latest_queue else None
            latest_queue_status = _normalize_existing_queue_status(latest_queue)

            active_parse_in_progress = latest_queue_status in active_statuses

            cursor.execute(
                """
                SELECT created_at
                FROM parsequeue
                WHERE business_id = %s
                  AND status IN ('completed', 'done')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (business_id_value,),
            )
            raw_completed_queue = cursor.fetchone()
            completed_queue = _row_to_dict(cursor, raw_completed_queue) if raw_completed_queue else None
            last_completed_at = _coerce_parse_datetime((completed_queue or {}).get("created_at"))

            if not last_completed_at:
                cursor.execute("SELECT last_parsed_at FROM businesses WHERE id = %s", (business_id_value,))
                raw_last_parsed = cursor.fetchone()
                last_parsed_row = _row_to_dict(cursor, raw_last_parsed) if raw_last_parsed else None
                last_completed_at = _coerce_parse_datetime((last_parsed_row or {}).get("last_parsed_at"))

            accepted_invites_count = 0
            if owner_id_value and invites_table_exists:
                cursor.execute(
                    """
                    SELECT COUNT(*) AS accepted_count
                    FROM invites
                    WHERE invited_by = %s
                      AND status = 'accepted'
                    """,
                    (owner_id_value,),
                )
                raw_invites = cursor.fetchone()
                invite_row = _row_to_dict(cursor, raw_invites) if raw_invites else None
                accepted_invites_count = int((invite_row or {}).get("accepted_count") or 0)

            invite_override_available = accepted_invites_count > 0
            cooldown_until = None
            weekly_cooldown_active = False
            if last_completed_at:
                cooldown_until = last_completed_at + timedelta(days=parse_refresh_cooldown_days)
                weekly_cooldown_active = cooldown_until > datetime.now()

            can_refresh_now = True
            reason = None
            message = None

            if active_parse_in_progress:
                can_refresh_now = False
                reason = "active_parse"
                message = "Сейчас уже идёт сбор данных. Дождитесь завершения текущего обновления."
            elif weekly_cooldown_active and not invite_override_available:
                can_refresh_now = False
                reason = "weekly_cooldown"
                cooldown_until_text = _serialize_parse_datetime(cooldown_until)
                if cooldown_until_text:
                    message = (
                        "Обновить данные карточки можно раз в неделю. "
                        f"Следующее обновление будет доступно после {cooldown_until_text}. "
                        "Если пригласить друга, обновление станет доступно раньше."
                    )
                else:
                    message = (
                        "Обновить данные карточки можно раз в неделю. "
                        "Если пригласить друга, обновление станет доступно раньше."
                    )

            return {
                "can_refresh": can_refresh_now,
                "reason": reason,
                "message": message,
                "cooldown_days": parse_refresh_cooldown_days,
                "last_completed_at": _serialize_parse_datetime(last_completed_at),
                "cooldown_until": _serialize_parse_datetime(cooldown_until),
                "invite_override_available": invite_override_available,
                "accepted_invites_count": accepted_invites_count,
            }

        def _humanize_parse_error_message(raw_message: Any) -> Optional[str]:
            message = str(raw_message or "").strip()
            if not message:
                return None

            lowered = message.lower()
            if "parsed entity mismatch for source url" not in lowered:
                return message

            bundle_match = re.search(r"bundle=([^\s]+)", message)
            bundle_path = str(bundle_match.group(1) if bundle_match else "").strip()
            if not bundle_path or not os.path.isdir(bundle_path):
                return message

            trace_path = os.path.join(bundle_path, "apify_trace.json")
            if not os.path.exists(trace_path):
                return message

            try:
                with open(trace_path, "r", encoding="utf-8") as fh:
                    trace_payload = json.load(fh)
            except Exception:
                return message

            if not isinstance(trace_payload, list):
                return message

            rejected_candidate = None
            for item in reversed(trace_payload):
                if not isinstance(item, dict):
                    continue
                if str(item.get("event") or "").strip() != "identity_filtered":
                    continue
                payload = item.get("payload")
                if not isinstance(payload, dict):
                    continue
                rejected_candidates = payload.get("rejected_candidates")
                if isinstance(rejected_candidates, list) and rejected_candidates:
                    first_candidate = rejected_candidates[0]
                    if isinstance(first_candidate, dict):
                        rejected_candidate = first_candidate
                        break

            if not isinstance(rejected_candidate, dict):
                return message

            candidate_name = str(rejected_candidate.get("name") or "").strip()
            candidate_city = str(rejected_candidate.get("city") or "").strip()
            candidate_address = str(rejected_candidate.get("address") or "").strip()
            details = []
            if candidate_name:
                details.append(f"название: {candidate_name}")
            if candidate_city:
                details.append(f"город: {candidate_city}")
            if candidate_address:
                details.append(f"адрес: {candidate_address}")
            if not details:
                return message

            return "Ссылка ведёт на другую карточку: " + "; ".join(details)

        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        user_id = user_data.get('user_id') or user_data.get('id')
        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем владельца
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        if owner_id != user_id and not db.is_superadmin(user_id):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        refresh_policy = _build_parse_refresh_policy(cursor, business_id, owner_id)

        cursor.execute("""
            SELECT status, retry_after, created_at, error_message
            FROM parsequeue
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """, (business_id,))
        raw_queue = cursor.fetchone()
        queue_row = _row_to_dict(cursor, raw_queue) if raw_queue else None

        retry_info = None
        overall_status = "idle"

        if queue_row:
            overall_status = normalize_status(queue_row.get("status") or "") or "idle"
            retry_after = queue_row.get("retry_after")

            # Вычисляем оставшееся время до повтора для статуса captcha
            if overall_status == 'captcha' and retry_after:
                try:
                    retry_dt = datetime.fromisoformat(retry_after)
                    now = datetime.now()
                    if retry_dt > now:
                        delta = retry_dt - now
                        hours = int(delta.total_seconds() / 3600)
                        minutes = int((delta.total_seconds() % 3600) / 60)
                        retry_info = {
                            'retry_after': retry_after,
                            'hours': hours,
                            'minutes': minutes
                        }
                        print(f"✅ Вычислен retry_info: {hours} ч {minutes} мин")
                    else:
                        print(f"⚠️ Время retry_after уже прошло: {retry_after} < {now}")
                        retry_info = None
                except Exception as e:
                    print(f"⚠️ Ошибка вычисления retry_info: {e}")
                    import traceback
                    traceback.print_exc()
                    retry_info = None
            else:
                if overall_status == 'captcha':
                    print(f"⚠️ Статус captcha, но retry_after отсутствует: {retry_after}")

        cursor.execute("""
            SELECT status, COUNT(*) AS count
            FROM parsequeue
            WHERE business_id = %s
            GROUP BY status
        """, (business_id,))
        status_rows = cursor.fetchall()

        statuses = {}
        for row in status_rows:
            rd = _row_to_dict(cursor, row)
            if rd:
                st = normalize_status(rd.get("status") or "idle")
                statuses[st] = statuses.get(st, 0) + (rd.get("count") or 0)

        # Определяем общий статус (если не определён выше из queue_row)
        # НЕ переопределяем статус, если он уже установлен из queue_row (например, captcha)
        if overall_status == "idle":
            if statuses.get('processing'):
                overall_status = "processing"
            elif statuses.get('pending') or statuses.get('queued'):
                overall_status = "queued"
            elif statuses.get('error'):
                overall_status = "error"
            elif statuses.get(STATUS_COMPLETED):
                overall_status = STATUS_COMPLETED
            elif statuses.get('captcha'):
                overall_status = "captcha"
                # Если статус captcha, но retry_info не был вычислен выше, вычисляем его здесь
                if retry_info is None:
                    cursor.execute("""
                        SELECT retry_after
                        FROM parsequeue
                        WHERE business_id = %s AND status = 'captcha'
                        ORDER BY created_at DESC
                        LIMIT 1
                    """, (business_id,))
                    raw_retry = cursor.fetchone()
                    retry_row = _row_to_dict(cursor, raw_retry) if raw_retry else None
                    if retry_row and retry_row.get("retry_after"):
                        try:
                            retry_dt = datetime.fromisoformat(str(retry_row["retry_after"]))
                            now = datetime.now()
                            if retry_dt > now:
                                delta = retry_dt - now
                                hours = int(delta.total_seconds() / 3600)
                                minutes = int((delta.total_seconds() % 3600) / 60)
                                retry_info = {
                                    'retry_after': retry_row[0],
                                    'hours': hours,
                                    'minutes': minutes
                                }
                                print(f"✅ Вычислен retry_info (fallback): {hours} ч {minutes} мин")
                        except Exception as e:
                            print(f"⚠️ Ошибка вычисления retry_info (fallback): {e}")

        if overall_status == "idle" and refresh_policy.get("reason") == "active_parse":
            overall_status = "processing"

        print(f"📊 Возвращаю статус: {overall_status}, retry_info: {retry_info}")
        db.close()
        raw_error_message = queue_row.get("error_message") if queue_row else None
        try:
            humanized_error_message = _humanize_parse_error_message(raw_error_message)
        except Exception:
            humanized_error_message = str(raw_error_message or "").strip() or None

        return jsonify({
            "success": True,
            "status": overall_status,
            "details": statuses,
            "retry_info": retry_info,
            "error_message": humanized_error_message,
            "refresh_policy": refresh_policy,
        })

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_parse_status: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_parse_status", "error_type": type(e).__name__, "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@app.route('/api/business/<string:business_id>/map-parses', methods=['GET'])
def get_map_parses(business_id):
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        user_id = user_data.get('user_id') or user_data.get('id')
        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем владельца
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        if owner_id != user_id and not db.is_superadmin(user_id):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        requested_scope = str(request.args.get("scope") or "").strip().lower()
        business_row, network_id, aggregate_network = _resolve_network_scope_for_business(cursor, business_id, requested_scope)

        # В PostgreSQL все результаты парсинга в cards. Берём реальные поля и считаем counts из JSONB.
        if aggregate_network:
            cursor.execute("""
                SELECT id, url, rating, reviews_count, report_path, created_at,
                       overview, products, news, photos, competitors, hours_full, ai_analysis
                FROM cards
                WHERE business_id = %s
                ORDER BY created_at DESC
            """, (business_id,))
        else:
            cursor.execute("""
                SELECT id, url, rating, reviews_count, report_path, created_at,
                       overview, products, news, photos, competitors, hours_full, ai_analysis
                FROM cards
                WHERE business_id = %s
                ORDER BY created_at DESC
            """, (business_id,))
        rows = cursor.fetchall()
        db.close()

        def _len(v):
            if v is None:
                return 0
            if isinstance(v, (list, dict)):
                return len(v)
            if isinstance(v, str):
                try:
                    p = json.loads(v)
                    return len(p) if isinstance(p, (list, dict)) else 0
                except Exception:
                    return 0
            return 0

        items = []
        for r in rows:
            rd = _row_to_dict(cursor, r)
            if not rd:
                continue
            news_count = _len(rd.get("news"))
            photos_count = _len(rd.get("photos"))
            products_count = _len(rd.get("products"))
            unanswered_reviews_count = 0
            if aggregate_network:
                ai_analysis = rd.get("ai_analysis")
                if isinstance(ai_analysis, str):
                    try:
                        ai_analysis = json.loads(ai_analysis) if ai_analysis.strip() else {}
                    except Exception:
                        ai_analysis = {}
                if not isinstance(ai_analysis, dict):
                    ai_analysis = {}
                network_audit = ai_analysis.get("network_audit") if isinstance(ai_analysis.get("network_audit"), dict) else {}
                summary = network_audit.get("summary") if isinstance(network_audit.get("summary"), dict) else {}
                news_count = int(summary.get("locations_with_news") or news_count or 0)
                photos_count = int(summary.get("locations_with_photos") or photos_count or 0)
                products_count = int(summary.get("locations_with_products") or products_count or 0)
                unanswered_reviews_count = int(summary.get("unanswered_imported_reviews_count") or 0)
            item = {
                "id": rd.get("id"),
                "url": rd.get("url"),
                "mapType": "yandex",
                "rating": rd.get("rating"),
                "reviewsCount": rd.get("reviews_count") or 0,
                "unansweredReviewsCount": unanswered_reviews_count,
                "newsCount": news_count,
                "photosCount": photos_count,
                "productsCount": products_count,
                "servicesCount": products_count,
                "reportPath": rd.get("report_path"),
                "createdAt": rd.get("created_at"),
                "scope": "network" if aggregate_network else "business",
            }
            items.append(item)

        return jsonify({"success": True, "items": items})

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_map_parses: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_map_parses", "error_type": type(e).__name__, "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@app.route('/api/map-report/<string:parse_id>', methods=['GET'])
def get_map_report(parse_id):
    try:
        # Авторизация
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        user_id = user_data.get('user_id') or user_data.get('id')

        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT c.report_path, c.business_id, b.owner_id
            FROM cards c
            LEFT JOIN businesses b ON c.business_id = b.id
            WHERE c.id = %s
            LIMIT 1
        """, (parse_id,))
        raw = cursor.fetchone()
        row = _row_to_dict(cursor, raw) if raw else None
        db.close()

        if not row:
            return jsonify({"error": "Отчет не найден"}), 404

        report_path = row.get("report_path")
        business_owner = row.get("owner_id")
        if business_owner != user_id:
            # Проверка суперадмина
            db2 = DatabaseManager()
            if not db2.is_superadmin(user_id):
                db2.close()
                return jsonify({"error": "Нет доступа"}), 403
            db2.close()

        if not report_path or not os.path.exists(report_path):
            return jsonify({"error": "Файл отчета недоступен"}), 404

        with open(report_path, 'r', encoding='utf-8') as f:
            html = f.read()
        return Response(html, mimetype='text/html')

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_map_report: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_map_report", "error_type": type(e).__name__, "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@app.route('/api/analyze-screenshot', methods=['POST'])
@rate_limit_if_available("20 per hour")
def analyze_screenshot():
    """Анализ скриншота карточки через GigaChat"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Проверяем наличие файла
        if 'image' not in request.files:
            return jsonify({"error": "Файл изображения не найден"}), 400

        file = request.files['image']
        if file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400

        # Проверяем тип файла
        allowed_types = ['image/png', 'image/jpeg', 'image/jpg']
        if file.content_type not in allowed_types:
            return jsonify({"error": "Неподдерживаемый тип файла. Разрешены: PNG, JPG, JPEG"}), 400

        # Проверяем размер файла (15 МБ)
        file.seek(0, 2)  # Переходим в конец файла
        file_size = file.tell()
        file.seek(0)  # Возвращаемся в начало

        if file_size > 15 * 1024 * 1024:  # 15 МБ
            return jsonify({"error": "Файл слишком большой. Максимум 15 МБ"}), 400

        # Читаем промпт из файла
        try:
            with open('prompts/cards-analysis-prompt.txt', 'r', encoding='utf-8') as f:
                prompt = f.read()
        except FileNotFoundError:
            prompt = """Проанализируй скриншот карточки организации на Яндекс.Картах.
ВЕРНИ РЕЗУЛЬТАТ СТРОГО В JSON ФОРМАТЕ:
{
  "completeness_score": число от 0 до 100,
  "business_name": "название из карточки",
  "category": "основная категория",
  "analysis": {
    "photos": {"count": количество_фото, "quality": "низкое/среднее/высокое", "recommendations": ["рекомендация1"]},
    "description": {"exists": true/false, "length": количество_символов, "seo_optimized": true/false, "recommendations": ["рекомендация1"]},
    "contacts": {"phone": true/false, "website": true/false, "social_media": true/false, "recommendations": ["рекомендация1"]},
    "schedule": {"complete": true/false, "recommendations": ["рекомендация1"]},
    "services": {"listed": true/false, "count": количество, "recommendations": ["рекомендация1"]}
  },
  "priority_actions": ["действие1", "действие2", "действие3"],
  "overall_recommendations": "общие рекомендации по улучшению"
}"""

        # Конвертируем изображение в base64
        image_data = file.read()
        image_base64 = base64.b64encode(image_data).decode('utf-8')

        # Анализируем через GigaChat
        business_id = get_business_id_from_user(user_data['user_id'])
        result = analyze_screenshot_with_gigachat(
            image_base64,
            prompt,
            business_id=business_id,
            user_id=user_data['user_id']
        )

        if 'error' in result:
            return jsonify({"error": result['error']}), 500

        # Сохраняем результат в БД
        db = DatabaseManager()
        analysis_id = str(uuid.uuid4())

        # Сохраняем файл
        upload_dir = 'uploads/screenshots'
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{analysis_id}.{file.filename.split('.')[-1]}")
        file.seek(0)
        file.save(file_path)

        # Сохраняем в БД
        cursor = db.conn.cursor()
        cursor.execute("""
            INSERT INTO screenshotanalyses (id, user_id, image_path, analysis_result, completeness_score, business_name, category, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            analysis_id,
            user_data['user_id'],
            file_path,
            json.dumps(result, ensure_ascii=False),
            result.get('completeness_score', 0),
            result.get('business_name', ''),
            result.get('category', ''),
            (datetime.now() + timedelta(days=1)).isoformat()
        ))
        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "analysis_id": analysis_id,
            "result": result
        })

    except Exception as e:
        print(f"❌ Ошибка анализа скриншота: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/optimize-pricelist', methods=['POST'])
def optimize_pricelist():
    """SEO оптимизация прайс-листа через GigaChat"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Проверяем наличие файла
        if 'file' not in request.files:
            return jsonify({"error": "Файл прайс-листа не найден"}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "Файл не выбран"}), 400

        # Проверяем тип файла
        allowed_types = ['application/pdf', 'application/msword',
                        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        'application/vnd.ms-excel',
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet']
        if file.content_type not in allowed_types:
            return jsonify({"error": "Неподдерживаемый тип файла. Разрешены: PDF, DOC, DOCX, XLS, XLSX"}), 400

        # Читаем промпт из файла
        try:
            with open('prompts/seo-optimization-prompt.txt', 'r', encoding='utf-8') as f:
                prompt = f.read()
        except FileNotFoundError:
            prompt = """Оптимизируй прайс-лист услуг для локального SEO и поисковых запросов.
КОНТЕКСТ: Салон красоты в России, целевые запросы включают географические модификаторы и коммерческие интенты.
ВЕРНИ РЕЗУЛЬТАТ В JSON:
{
  "services": [
    {
      "original_name": "исходное название",
      "optimized_name": "SEO-оптимизированное название",
      "seo_description": "описание 120-150 символов для сайта/карт",
      "keywords": ["ключ1", "ключ2", "ключ3"],
      "price": "цена если указана",
      "category": "категория услуги"
    }
  ],
  "general_recommendations": ["рекомендация по структуре прайса", "рекомендация по ключевым словам"]
}
ТРЕБОВАНИЯ:
- Названия до 60 символов
- Описания 120-150 символов
- Включай местные модификаторы при необходимости
- Используй коммерческие интенты в формулировках"""

        # Читаем содержимое файла (упрощенная версия - только текст)
        file_content = file.read().decode('utf-8', errors='ignore')

        # Формируем полный промпт с данными файла
        full_prompt = f"{prompt}\n\nДанные прайс-листа:\n{file_content[:2000]}"  # Ограничиваем размер

        # Анализируем через GigaChat
        result = analyze_text_with_gigachat(full_prompt)

        if 'error' in result:
            return jsonify({"error": result['error']}), 500

        # Сохраняем результат в БД
        db = DatabaseManager()
        optimization_id = str(uuid.uuid4())

        # Сохраняем файл
        upload_dir = 'uploads/pricelists'
        os.makedirs(upload_dir, exist_ok=True)
        file_path = os.path.join(upload_dir, f"{optimization_id}_{file.filename}")
        file.seek(0)
        file.save(file_path)

        # Сохраняем в БД
        cursor = db.conn.cursor()
        services_count = len(result.get('services', [])) if isinstance(result.get('services'), list) else 0
        cursor.execute("""
            INSERT INTO PricelistOptimizations (id, user_id, original_file_path, optimized_data, services_count, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            optimization_id,
            user_data['user_id'],
            file_path,
            json.dumps(result, ensure_ascii=False),
            services_count,
            (datetime.now() + timedelta(days=1)).isoformat()
        ))
        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "optimization_id": optimization_id,
            "result": result
        })

    except Exception as e:
        print(f"❌ Ошибка оптимизации прайс-листа: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analysis/<analysis_id>', methods=['GET'])
def get_analysis(analysis_id):
    """Получить результат анализа по ID"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Ищем анализ скриншота
        cursor.execute("""
            SELECT * FROM screenshotanalyses
            WHERE id = %s AND user_id = %s AND expires_at > %s
        """, (analysis_id, user_data['user_id'], datetime.now().isoformat()))

        analysis = cursor.fetchone()
        if analysis:
            analysis_data = _row_to_dict(cursor, analysis) if analysis else {}
            db.close()
            return jsonify({
                "success": True,
                "type": "screenshot",
                "result": json.loads(analysis_data.get('analysis_result') or "{}"),
                "created_at": analysis_data.get('created_at')
            })

        # Ищем оптимизацию прайс-листа
        cursor.execute("""
            SELECT * FROM pricelistoptimizations
            WHERE id = %s AND user_id = %s AND expires_at > %s
        """, (analysis_id, user_data['user_id'], datetime.now().isoformat()))

        optimization = cursor.fetchone()
        if optimization:
            optimization_data = _row_to_dict(cursor, optimization) if optimization else {}
            db.close()
            return jsonify({
                "success": True,
                "type": "pricelist",
                "result": json.loads(optimization_data.get('optimized_data') or "{}"),
                "created_at": optimization_data.get('created_at')
            })

        db.close()
        return jsonify({"error": "Анализ не найден или истек срок действия"}), 404

    except Exception as e:
        print(f"❌ Ошибка получения анализа: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/analyze-card-auto', methods=['POST'])
@rate_limit_if_available("20 per hour")
def analyze_card_auto():
    """Автоматический анализ карточки компании на Яндекс.Картах"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json()
        yandex_url = data.get('url')

        if not yandex_url:
            return jsonify({"error": "URL карточки обязателен"}), 400

        # Проверяем, что это URL Яндекс.Карт
        if 'yandex.ru/maps' not in yandex_url:
            return jsonify({"error": "Неверный URL. Требуется ссылка на Яндекс.Карты"}), 400

        # Импортируем модуль автоматического скриншота
        from automated_screenshot import YandexMapsScreenshotter

        # Создаем скриншот и анализируем
        screenshotter = YandexMapsScreenshotter(headless=True)
        result = screenshotter.analyze_card_from_url(yandex_url)

        if not result:
            return jsonify({"error": "Не удалось проанализировать карточку"}), 500

        # Сохраняем результат в базу данных
        db = DatabaseManager()
        cursor = db.conn.cursor()

        analysis_id = str(uuid.uuid4())
        expires_at = (datetime.now() + timedelta(days=7)).isoformat()

        cursor.execute("""
            INSERT INTO screenshotanalyses
            (id, user_id, analysis_result, completeness_score, business_name, category, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            analysis_id,
            user_data['user_id'],
            json.dumps(result),
            result.get('completeness_score', 0),
            result.get('business_name', ''),
            result.get('category', ''),
            expires_at
        ))

        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "analysis_id": analysis_id,
            "result": result,
            "message": "Карточка успешно проанализирована"
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка автоматического анализа: {str(e)}"}), 500

@app.route('/api/gigachat/config', methods=['GET'])
def get_gigachat_config():
    """Получить текущую конфигурацию GigaChat"""
    try:
        from gigachat_config import get_gigachat_config, get_available_models

        config = get_gigachat_config()
        available_models = get_available_models()

        return jsonify({
            "success": True,
            "current_config": config.get_model_config(),
            "model_info": config.get_model_info(),
            "available_models": available_models
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка получения конфигурации: {str(e)}"}), 500

@app.route('/api/gigachat/config', methods=['POST'])
def set_gigachat_config():
    """Изменить конфигурацию GigaChat"""
    try:
        from gigachat_config import set_gigachat_model

        data = request.get_json()
        model_name = data.get('model')

        if not model_name:
            return jsonify({"error": "Модель не указана"}), 400

        if set_gigachat_model(model_name):
            return jsonify({
                "success": True,
                "message": f"Модель изменена на {model_name}",
                "model": model_name
            })
        else:
            return jsonify({"error": f"Модель {model_name} не поддерживается"}), 400

    except Exception as e:
        return jsonify({"error": f"Ошибка изменения конфигурации: {str(e)}"}), 500

@app.route('/api/gigachat/diagnostics', methods=['GET'])
def gigachat_diagnostics():
    """Проверка загрузки ключей и получения access_token у GigaChat"""
    try:
        from services.gigachat_client import get_gigachat_client
        client = get_gigachat_client()

        # Проверим наличие ключей в пуле
        creds_count = len(client.credentials_pool)
        model_cfg = client.config.get_model_config()

        token_ok = False
        token_error = None
        try:
            token = client.get_access_token()
            token_ok = bool(token)
        except Exception as e:
            token_error = str(e)

        return jsonify({
            "success": token_ok,
            "credentials_loaded": creds_count,
            "current_key_index": client.current_index if creds_count else None,
            "model": model_cfg.get("model"),
            "temperature": model_cfg.get("temperature"),
            "max_tokens": model_cfg.get("max_tokens"),
            "token_error": token_error
        }), (200 if token_ok else 503)
    except Exception as e:
        return jsonify({"error": f"Диагностика не удалась: {str(e)}"}), 500

@app.route('/api/networks/<string:network_id>/locations', methods=['GET'])
def get_network_locations_by_network_id(network_id):
    """Получить список точек сети"""
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

        # Проверяем, что пользователь имеет доступ к сети
        cursor.execute("SELECT owner_id FROM networks WHERE id = %s", (network_id,))
        raw_network = cursor.fetchone()
        network = _row_to_dict(cursor, raw_network) if raw_network else None

        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404

        # Проверяем права доступа (владелец или суперадмин)
        if network.get("owner_id") != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этой сети"}), 403

        # Получаем точки сети
        cursor.execute("""
            SELECT id, name, address, description
            FROM businesses
            WHERE network_id = %s
            ORDER BY name
        """, (network_id,))

        locations = []
        for row in cursor.fetchall():
            row_data = _row_to_dict(cursor, row) if row else {}
            locations.append({
                "id": row_data.get("id"),
                "name": row_data.get("name"),
                "address": row_data.get("address"),
                "description": row_data.get("description")
            })

        db.close()

        return jsonify({
            "success": True,
            "locations": locations
        })

    except Exception as e:
        return jsonify({"error": f"Ошибка получения точек сети: {str(e)}"}), 500
