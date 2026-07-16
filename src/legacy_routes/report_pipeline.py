from legacy_routes import shared as _shared

globals().update(_shared.runtime_namespace)

@app.route('/api/telegram/bind/verify', methods=['POST'])
def verify_telegram_bind_token():
    """Проверка токена привязки (вызывается из бота)"""
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400

        bind_token = data.get('token', '').strip()
        telegram_id = data.get('telegram_id', '').strip()

        if not bind_token or not telegram_id:
            return jsonify({"error": "Токен и telegram_id обязательны"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()

        cursor.execute(
            """
            SELECT id, user_id, business_id, expires_at, used
            FROM telegrambindtokens
            WHERE token = %s
            """,
            (bind_token,),
        )
        token_row = cursor.fetchone()
        if token_row:
            token_id, user_id, business_id_from_token, expires_at, used = token_row

        if not token_row:
            db.close()
            return jsonify({"error": "Токен не найден"}), 404

        # Проверяем срок действия
        from datetime import datetime
        expires_dt = expires_at
        if isinstance(expires_at, str):
            expires_dt = datetime.fromisoformat(expires_at)
        if expires_dt < datetime.now(expires_dt.tzinfo) if getattr(expires_dt, "tzinfo", None) else datetime.now():
            db.close()
            return jsonify({"error": "Токен истек"}), 400

        # Проверяем, не использован ли уже
        if used:
            db.close()
            return jsonify({"error": "Токен уже использован"}), 400

        # Проверяем, не привязан ли уже этот Telegram к другому аккаунту
        cursor.execute("SELECT id FROM users WHERE telegram_id = %s AND id != %s", (telegram_id, user_id))
        existing_user = cursor.fetchone()
        if existing_user:
            db.close()
            return jsonify({"error": "Этот Telegram уже привязан к другому аккаунту"}), 400

        # Привязываем Telegram к аккаунту
        cursor.execute("""
            UPDATE users
            SET telegram_id = %s, updated_at = %s
            WHERE id = %s
        """, (telegram_id, datetime.now(), user_id))

        # Помечаем токен как использованный
        cursor.execute(
            """
            UPDATE telegrambindtokens
            SET used = 1,
                business_id = COALESCE(%s, business_id)
            WHERE id = %s
            """,
            (business_id_from_token, token_id),
        )

        db.conn.commit()

        # Получаем информацию о пользователе
        cursor.execute("SELECT email, name FROM users WHERE id = %s", (user_id,))
        user_info = cursor.fetchone()

        db.close()

        return jsonify({
            "success": True,
            "user": {
                "id": user_id,
                "email": user_info[0] if user_info else None,
                "name": user_info[1] if user_info else None
            }
        }), 200

    except Exception as e:
        print(f"❌ Ошибка проверки токена привязки: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/public/contact', methods=['POST', 'OPTIONS'])
@rate_limit_if_available("10 per hour")
def public_contact():
    """Обработка формы обратной связи"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400

        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        message = data.get('message', '').strip()

        if not name or not email or not message:
            return jsonify({"error": "Имя, email и сообщение обязательны"}), 400

        # Логирование в консоль
        print(f"📧 НОВОЕ СООБЩЕНИЕ ОТ {name} ({email}):")
        print(f"📞 Телефон: {phone}")
        print(f"💬 Сообщение: {message}")
        print("-" * 50)

        # Отправка email
        email_sent = send_contact_email(name, email, phone, message)
        if not email_sent:
            print("⚠️ Не удалось отправить email с формы обратной связи")
            return jsonify({"error": "Не удалось отправить сообщение. Попробуйте позже."}), 503

        return jsonify({"success": True, "message": "Сообщение отправлено"})

    except Exception as e:
        print(f"❌ Ошибка обработки формы обратной связи: {e}")
        return jsonify({"error": str(e)}), 500

def _slugify_public_report_name(name: str) -> str:
    raw = str(name or "").strip().lower()
    converted: list[str] = []
    for ch in raw:
        if "a" <= ch <= "z" or "0" <= ch <= "9":
            converted.append(ch)
            continue
        if "а" <= ch <= "я" or ch == "ё":
            converted.append(_RU_LAT.get(ch, ""))
            continue
        if ch in _EXTRA_LAT:
            converted.append(_EXTRA_LAT.get(ch, ""))
            continue
        if ch in {" ", "-", "_", ".", ",", "/", "|", ":"}:
            converted.append("-")
    slug = re.sub(r"-{2,}", "-", "".join(converted)).strip("-")
    return slug or f"report-{uuid.uuid4().hex[:8]}"

def _detect_public_map_source(url: str) -> str:
    value = str(url or "").lower()
    if "2gis." in value:
        return "apify_2gis"
    if is_google_map_url(value):
        return "apify_google"
    if "maps.apple.com/" in value:
        return "apify_apple"
    return "apify_yandex"

def _normalize_public_media_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("//"):
        text = f"https:{text}"
    if "{size}" in text:
        text = text.replace("{size}", "XXXL")
    if "/%s" in text:
        text = text.replace("/%s", "/XXXL")
    elif "%s" in text:
        text = text.replace("%s", "XXXL")
    return text

def _extract_public_street(address: str) -> str:
    text = str(address or "").strip()
    if not text:
        return ""
    parts = [part.strip() for part in text.split(",") if str(part or "").strip()]
    if not parts:
        return ""
    street_tokens = (
        "улиц", "ул.", "просп", "наб", "шоссе", "бульвар", "переул", "коса",
        "street", "st", "ave", "road", "rd", "blvd",
        "sok", "sok.", "sokak", "cad", "cad.", "caddesi", "mah", "mah.", "mahalle",
    )
    for part in parts:
        lower_part = part.lower()
        if any(token in lower_part for token in street_tokens):
            return part
    first = parts[0]
    if any(ch.isdigit() for ch in first) and len(parts) >= 2:
        second = parts[1]
        if second and not any(ch.isdigit() for ch in second):
            return f"{first}, {second}"
    return first

def _build_public_report_display_name(name: str, city: str, address: str) -> str:
    business_name = str(name or "").strip() or "Компания"
    city_name = str(city or "").strip()
    if not city_name:
        city_name = str(address or "").split(",", 1)[0].strip()
    street_name = _extract_public_street(address)
    parts = [business_name]
    if city_name:
        parts.append(city_name)
    if street_name:
        parts.append(street_name)
    return " — ".join(parts)

def _normalize_public_map_source_name(source_value: Any) -> str:
    source_name = str(source_value or "").strip().lower()
    if source_name in {"apify_yandex", "yandex_maps", "yandex_business", "yandex"}:
        return "yandex_maps"
    if source_name in {"apify_google", "google_maps", "google_business", "google"}:
        return "google_maps"
    if source_name in {"apify_2gis", "2gis", "two_gis"}:
        return "2gis"
    if source_name in {"apify_apple", "apple_maps", "apple"}:
        return "apple_maps"
    return source_name or "unknown"

def _public_map_source_label(source_value: Any) -> str:
    normalized = _normalize_public_map_source_name(source_value)
    if normalized == "yandex_maps":
        return "Яндекс Карты"
    if normalized == "google_maps":
        return "Google Maps"
    if normalized == "2gis":
        return "2ГИС"
    if normalized == "apple_maps":
        return "Apple Maps"
    return normalized

def _build_public_maps_analysis(cursor, business_id: str) -> List[Dict[str, Any]]:
    business_id_value = str(business_id or "").strip()
    if not business_id_value:
        return []

    cursor.execute(
        """
        SELECT url, map_type
        FROM businessmaplinks
        WHERE business_id = %s
        ORDER BY created_at ASC
        """,
        (business_id_value,),
    )
    map_links_rows = [_row_to_dict(cursor, row) for row in cursor.fetchall() or []]

    cursor.execute(
        """
        SELECT source, rating, reviews_total, date
        FROM externalbusinessstats
        WHERE business_id = %s
        ORDER BY date DESC
        """,
        (business_id_value,),
    )
    stats_rows = [_row_to_dict(cursor, row) for row in cursor.fetchall() or []]

    sources: Dict[str, Dict[str, Any]] = {}

    for item in map_links_rows:
        source_name = _normalize_public_map_source_name(item.get("map_type"))
        if source_name == "unknown":
            continue
        source_entry = sources.get(source_name) or {
            "source": source_name,
            "label": _public_map_source_label(source_name),
            "url": None,
            "rating": None,
            "reviews_total": None,
            "last_sync_at": None,
        }
        url_value = str(item.get("url") or "").strip()
        if url_value and not source_entry.get("url"):
            source_entry["url"] = url_value
        sources[source_name] = source_entry

    for item in stats_rows:
        source_name = _normalize_public_map_source_name(item.get("source"))
        if source_name == "unknown":
            continue
        source_entry = sources.get(source_name) or {
            "source": source_name,
            "label": _public_map_source_label(source_name),
            "url": None,
            "rating": None,
            "reviews_total": None,
            "last_sync_at": None,
        }
        source_entry["rating"] = item.get("rating")
        source_entry["reviews_total"] = int(item.get("reviews_total") or 0)
        source_entry["last_sync_at"] = item.get("date")
        sources[source_name] = source_entry

    ordered = list(sources.values())
    ordered.sort(
        key=lambda item: (
            0 if item.get("source") == "google_maps" else 1 if item.get("source") == "yandex_maps" else 2,
            str(item.get("label") or ""),
        )
    )
    return ordered

def _to_json_compatible(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, inner in value.items():
            normalized[str(key)] = _to_json_compatible(inner)
        return normalized
    if isinstance(value, (list, tuple, set)):
        return [_to_json_compatible(item) for item in value]
    return value

def _build_public_pending_page(*, email: str, map_url: str) -> dict[str, Any]:
    return {
        "processing": True,
        "processing_message": "Здесь появится ваш отчёт, как только он будет готов.",
        "name": "Ваш отчёт готовится",
        "category": "Аудит карточки на картах",
        "source_url": map_url,
        "audit": {
            "summary_score": 0,
            "health_level": "processing",
            "health_label": "Готовим отчёт",
            "summary_text": "Мы уже парсим карточку и собираем данные. Обычно это занимает 1–3 минуты.",
            "findings": [],
            "recommended_actions": [
                {
                    "title": "Собираем фактические данные карточки",
                    "description": "Подтягиваем услуги, отзывы, рейтинг, фото и контакты из карты.",
                },
                {
                    "title": "Формируем персональный аудит",
                    "description": "После парсинга покажем конкретные шаги роста именно для вашей карточки.",
                },
            ],
            "services_preview": [],
            "reviews_preview": [],
            "news_preview": [],
            "subscores": {},
            "current_state": {
                "rating": None,
                "reviews_count": 0,
                "unanswered_reviews_count": 0,
                "services_count": 0,
                "services_with_price_count": 0,
                "has_website": False,
                "has_recent_activity": False,
                "photos_state": "unknown",
            },
            "revenue_potential": {},
            "cadence": {
                "news_posts_per_month_min": 4,
                "photos_per_month_min": 8,
                "reviews_response_hours_max": 48,
            },
        },
        "cta": {
            "email": email,
            "telegram_url": None,
            "whatsapp_url": None,
            "website": None,
        },
        "updated_at": datetime.utcnow().isoformat(),
    }

def _public_report_url(slug: str) -> str:
    frontend_base = str(os.getenv("FRONTEND_BASE_URL") or os.getenv("PUBLIC_DOMAIN") or "https://localos.pro").strip().rstrip("/")
    return f"{frontend_base}/{str(slug or '').strip().lstrip('/')}" if frontend_base else f"/{str(slug or '').strip().lstrip('/')}"

def _notify_public_report_request_async(email: str, url: str, public_url: str) -> None:
    contact_email = os.getenv("CONTACT_EMAIL", "info@localos.pro")
    subject = f"Новая заявка с сайта LocalOS от {email}"
    body = f"""
Новая заявка с сайта LocalOS

Email клиента: {email}
Ссылка на бизнес: {url}
Публичная страница отчёта: {public_url}

---
Отправлено с сайта localos.pro
    """

    def _send() -> None:
        try:
            email_sent = send_email(contact_email, subject, body)
            if not email_sent:
                print("⚠️ Не удалось отправить email по новой публичной заявке")
        except Exception as exc:
            print(f"⚠️ Ошибка фонового email по публичной заявке: {exc}")

    threading.Thread(target=_send, daemon=True).start()

def _send_public_report_ready_telegram(page_json: dict[str, Any], slug: str) -> bool:
    notification = page_json.get("telegram_notification") if isinstance(page_json.get("telegram_notification"), dict) else {}
    if not notification or notification.get("sent_at"):
        return False
    if not bool(notification.get("notify_when_ready")):
        return False

    chat_id = str(notification.get("chat_id") or "").strip()
    token = str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not chat_id or not token:
        return False

    name = str(page_json.get("display_name") or page_json.get("name") or "карточке").strip()
    public_url = _public_report_url(slug)
    text = (
        "✅ Аудит готов.\n\n"
        f"Карточка: {name}\n"
        f"Открыть аудит: {public_url}\n\n"
        "Посмотрите, где карточка теряет клиентов, и начните исправлять это в LocalOS."
    )
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={
                "chat_id": chat_id,
                "text": text,
                "disable_web_page_preview": True,
            },
            timeout=15,
            **build_requests_proxy_kwargs(),
        )
        if response.ok:
            notification["sent_at"] = datetime.utcnow().isoformat()
            notification["status"] = "sent"
            page_json["telegram_notification"] = notification
            return True
        notification["status"] = "error"
        notification["error"] = f"HTTP {response.status_code}"
        page_json["telegram_notification"] = notification
        return False
    except Exception as exc:
        notification["status"] = "error"
        notification["error"] = str(exc)
        page_json["telegram_notification"] = notification
        return False

def _ensure_public_report_requests_table(conn) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS publicreportrequests (
            slug TEXT PRIMARY KEY,
            email TEXT NOT NULL,
            source_url TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'apify_yandex',
            status TEXT NOT NULL DEFAULT 'queued',
            page_json JSONB NOT NULL,
            result_json JSONB,
            error_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    conn.commit()

def _is_public_offer_slug(path: str) -> bool:
    slug = str(path or "").strip().strip("/")
    if not slug or "/" in slug or "." in slug:
        return False
    if slug in PUBLIC_AUDIT_APP_ROUTES:
        return False

    conn = None
    try:
        conn = get_db_connection()
        _ensure_public_report_requests_table(conn)
        _ensure_partnership_public_offers_table(conn)
        _ensure_admin_prospecting_public_offers_table(conn)
        cur = conn.cursor()

        cur.execute(
            """
            SELECT 1
            FROM partnershippublicoffers
            WHERE slug = %s
              AND is_active = TRUE
            LIMIT 1
            """,
            (_slugify_company_name(slug),),
        )
        if cur.fetchone():
            return True

        cur.execute(
            """
            SELECT 1
            FROM adminprospectingleadpublicoffers
            WHERE slug = %s
              AND is_active = TRUE
            LIMIT 1
            """,
            (_slugify_company_name(slug),),
        )
        if cur.fetchone():
            return True

        cur.execute(
            """
            SELECT 1
            FROM publicreportrequests
            WHERE slug = %s
            LIMIT 1
            """,
            (_slugify_public_report_name(slug),),
        )
        return cur.fetchone() is not None
    except Exception as e:
        print(f"public audit slug lookup failed for '{slug}': {e}")
        return False
    finally:
        if conn:
            conn.close()

def _run_public_report_pipeline(slug: str) -> None:
    conn = None
    try:
        conn = get_db_connection()
        _ensure_public_report_requests_table(conn)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT slug, email, source_url, source, page_json
            FROM publicreportrequests
            WHERE slug = %s
            LIMIT 1
            """,
            (slug,),
        )
        row = cur.fetchone()
        if not row:
            return
        payload = dict(row) if hasattr(row, "keys") else {
            "slug": row[0],
            "email": row[1],
            "source_url": row[2],
            "source": row[3],
            "page_json": row[4],
        }
        raw_source_url = str(payload.get("source_url") or "").strip()
        source_url = normalize_map_url(raw_source_url) or raw_source_url
        source = str(payload.get("source") or "apify_yandex").strip().lower()
        email = str(payload.get("email") or "").strip()
        existing_page_json = payload.get("page_json")
        if isinstance(existing_page_json, str):
            try:
                existing_page_json = json.loads(existing_page_json)
            except Exception:
                existing_page_json = {}
        if not isinstance(existing_page_json, dict):
            existing_page_json = {}
        existing_telegram_notification = (
            existing_page_json.get("telegram_notification")
            if isinstance(existing_page_json.get("telegram_notification"), dict)
            else None
        )

        cur.execute(
            "UPDATE publicreportrequests SET status = %s, updated_at = NOW() WHERE slug = %s",
            ("processing", slug),
        )
        conn.commit()

        service = ProspectingService(source=source)
        run_result = service.run_business_by_map_url(source_url, limit=1, timeout_sec=320)
        items = run_result.get("items") if isinstance(run_result, dict) else []
        first_item = items[0] if isinstance(items, list) and items else {}
        if not isinstance(first_item, dict) or not first_item:
            raise RuntimeError("Парсер не вернул данные по карточке")

        lead_like = {
            "id": f"public-{slug}",
            "name": first_item.get("name"),
            "category": first_item.get("category"),
            "city": first_item.get("city"),
            "address": first_item.get("address"),
            "website": first_item.get("website"),
            "phone": first_item.get("phone"),
            "email": first_item.get("email") or email,
            "rating": first_item.get("rating"),
            "reviews_count": first_item.get("reviews_count"),
            "source_url": first_item.get("source_url") or source_url,
            "telegram_url": first_item.get("telegram_url"),
            "whatsapp_url": first_item.get("whatsapp_url"),
            "search_payload_json": first_item.get("search_payload_json"),
            "reviews_json": first_item.get("reviews_json"),
            "services_json": first_item.get("services_json"),
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }

        snapshot = _to_json_compatible(build_lead_card_preview_snapshot(lead_like))
        preview_meta = snapshot.get("preview_meta") if isinstance(snapshot.get("preview_meta"), dict) else {}
        matched_business_id = str(preview_meta.get("business_id") or "").strip()
        canonical_audit = snapshot
        if matched_business_id:
            try:
                business_snapshot = _to_json_compatible(build_card_audit_snapshot(matched_business_id))
                if isinstance(business_snapshot, dict) and business_snapshot:
                    def _audit_signal_score(audit_payload: Dict[str, Any]) -> int:
                        current_state = audit_payload.get("current_state") if isinstance(audit_payload.get("current_state"), dict) else {}
                        score = 0
                        if current_state.get("rating") not in (None, ""):
                            score += 3
                        if int(current_state.get("reviews_count") or 0) > 0:
                            score += 2
                        if int(current_state.get("services_count") or 0) > 0:
                            score += 2
                        if bool(current_state.get("description_present")):
                            score += 1
                        if isinstance(audit_payload.get("reviews_preview"), list) and audit_payload.get("reviews_preview"):
                            score += 2
                        if isinstance(audit_payload.get("services_preview"), list) and audit_payload.get("services_preview"):
                            score += 2
                        return score

                    snapshot_score = _audit_signal_score(snapshot)
                    business_score = _audit_signal_score(business_snapshot)
                    preferred_audit = business_snapshot if business_score >= snapshot_score else snapshot
                    fallback_audit = snapshot if preferred_audit is business_snapshot else business_snapshot

                    def _pick_list(key: str) -> Any:
                        preferred_value = preferred_audit.get(key)
                        if isinstance(preferred_value, list) and preferred_value:
                            return preferred_value
                        fallback_value = fallback_audit.get(key)
                        if isinstance(fallback_value, list):
                            return fallback_value
                        return preferred_value if isinstance(preferred_value, list) else []

                    def _pick_dict(key: str) -> Any:
                        preferred_value = preferred_audit.get(key)
                        if isinstance(preferred_value, dict) and preferred_value:
                            return preferred_value
                        fallback_value = fallback_audit.get(key)
                        if isinstance(fallback_value, dict):
                            return fallback_value
                        return preferred_value if isinstance(preferred_value, dict) else {}

                    canonical_audit = {
                        **snapshot,
                        "summary_score": preferred_audit.get("summary_score") if preferred_audit.get("summary_score") not in (None, "") else fallback_audit.get("summary_score"),
                        "health_level": preferred_audit.get("health_level") or fallback_audit.get("health_level"),
                        "health_label": preferred_audit.get("health_label") or fallback_audit.get("health_label"),
                        "summary_text": preferred_audit.get("summary_text") or fallback_audit.get("summary_text"),
                        "findings": _pick_list("findings"),
                        "recommended_actions": _pick_list("recommended_actions"),
                        "issue_blocks": _pick_list("issue_blocks"),
                        "top_3_issues": _pick_list("top_3_issues"),
                        "action_plan": _pick_dict("action_plan"),
                        "subscores": _pick_dict("subscores"),
                        "current_state": _pick_dict("current_state"),
                        "revenue_potential": _pick_dict("revenue_potential"),
                        "parse_context": _pick_dict("parse_context"),
                        "cadence": _pick_dict("cadence"),
                        "audit_profile": preferred_audit.get("audit_profile") or fallback_audit.get("audit_profile"),
                        "audit_profile_label": preferred_audit.get("audit_profile_label") or fallback_audit.get("audit_profile_label"),
                        "best_fit_customer_profile": _pick_list("best_fit_customer_profile"),
                        "weak_fit_customer_profile": _pick_list("weak_fit_customer_profile"),
                        "best_fit_guest_profile": _pick_list("best_fit_guest_profile"),
                        "weak_fit_guest_profile": _pick_list("weak_fit_guest_profile"),
                        "search_intents_to_target": _pick_list("search_intents_to_target"),
                        "photo_shots_missing": _pick_list("photo_shots_missing"),
                        "positioning_focus": _pick_list("positioning_focus"),
                        "strength_themes": _pick_list("strength_themes"),
                        "objection_themes": _pick_list("objection_themes"),
                        "reviews_preview": _pick_list("reviews_preview"),
                        "services_preview": _pick_list("services_preview"),
                        "news_preview": _pick_list("news_preview"),
                    }
            except Exception as merge_exc:
                print(f"public report merge fallback for slug={slug}: {merge_exc}")
        preview_meta = canonical_audit.get("preview_meta") if isinstance(canonical_audit.get("preview_meta"), dict) else preview_meta
        logo_url = _normalize_public_media_url(preview_meta.get("logo_url") if isinstance(preview_meta, dict) else "")
        photo_urls = []
        photo_values = preview_meta.get("photo_urls") if isinstance(preview_meta, dict) else []
        if isinstance(photo_values, list):
            for item in photo_values:
                media_url = _normalize_public_media_url(item)
                if media_url:
                    photo_urls.append(media_url)

        maps_analysis = []
        display_name = _build_public_report_display_name(
            lead_like.get("name"),
            lead_like.get("city"),
            lead_like.get("address"),
        )
        if matched_business_id:
            try:
                maps_analysis = _to_json_compatible(_build_public_maps_analysis(cur, matched_business_id))
            except Exception as maps_exc:
                print(f"public report maps analysis fallback for slug={slug}: {maps_exc}")
        if not maps_analysis:
            maps_analysis = []
        fresh_reviews_total = first_item.get("reviews_count")
        fresh_rating_value = first_item.get("rating")
        for item in maps_analysis:
            if not isinstance(item, dict):
                continue
            if str(item.get("source") or "").strip().lower() == "google_maps":
                if item.get("rating") in (None, "") and fresh_rating_value not in (None, ""):
                    item["rating"] = fresh_rating_value
                if item.get("reviews_total") in (None, "") and fresh_reviews_total not in (None, ""):
                    item["reviews_total"] = fresh_reviews_total

        page_json = {
            "processing": False,
            "name": lead_like.get("name") or "Компания",
            "display_name": display_name,
            "category": lead_like.get("category"),
            "city": lead_like.get("city"),
            "address": lead_like.get("address"),
            "source_url": lead_like.get("source_url"),
            "logo_url": logo_url or None,
            "photo_urls": photo_urls[:8],
            "maps_analysis": maps_analysis if isinstance(maps_analysis, list) else [],
            "audit": {
                "summary_score": canonical_audit.get("summary_score"),
                "health_level": canonical_audit.get("health_level"),
                "health_label": canonical_audit.get("health_label"),
                "summary_text": canonical_audit.get("summary_text"),
                "findings": canonical_audit.get("findings") if isinstance(canonical_audit.get("findings"), list) else [],
                "recommended_actions": canonical_audit.get("recommended_actions") if isinstance(canonical_audit.get("recommended_actions"), list) else [],
                "services_preview": canonical_audit.get("services_preview") if isinstance(canonical_audit.get("services_preview"), list) else [],
                "subscores": canonical_audit.get("subscores") if isinstance(canonical_audit.get("subscores"), dict) else {},
                "current_state": canonical_audit.get("current_state") if isinstance(canonical_audit.get("current_state"), dict) else {},
                "parse_context": canonical_audit.get("parse_context") if isinstance(canonical_audit.get("parse_context"), dict) else {},
                "revenue_potential": canonical_audit.get("revenue_potential") if isinstance(canonical_audit.get("revenue_potential"), dict) else {},
                "reviews_preview": canonical_audit.get("reviews_preview") if isinstance(canonical_audit.get("reviews_preview"), list) else [],
                "news_preview": canonical_audit.get("news_preview") if isinstance(canonical_audit.get("news_preview"), list) else [],
                "issue_blocks": canonical_audit.get("issue_blocks") if isinstance(canonical_audit.get("issue_blocks"), list) else [],
                "top_3_issues": canonical_audit.get("top_3_issues") if isinstance(canonical_audit.get("top_3_issues"), list) else [],
                "action_plan": canonical_audit.get("action_plan") if isinstance(canonical_audit.get("action_plan"), dict) else {},
                "audit_profile": canonical_audit.get("audit_profile"),
                "audit_profile_label": canonical_audit.get("audit_profile_label"),
                "best_fit_customer_profile": canonical_audit.get("best_fit_customer_profile") if isinstance(canonical_audit.get("best_fit_customer_profile"), list) else [],
                "weak_fit_customer_profile": canonical_audit.get("weak_fit_customer_profile") if isinstance(canonical_audit.get("weak_fit_customer_profile"), list) else [],
                "best_fit_guest_profile": canonical_audit.get("best_fit_guest_profile") if isinstance(canonical_audit.get("best_fit_guest_profile"), list) else [],
                "weak_fit_guest_profile": canonical_audit.get("weak_fit_guest_profile") if isinstance(canonical_audit.get("weak_fit_guest_profile"), list) else [],
                "search_intents_to_target": canonical_audit.get("search_intents_to_target") if isinstance(canonical_audit.get("search_intents_to_target"), list) else [],
                "photo_shots_missing": canonical_audit.get("photo_shots_missing") if isinstance(canonical_audit.get("photo_shots_missing"), list) else [],
                "positioning_focus": canonical_audit.get("positioning_focus") if isinstance(canonical_audit.get("positioning_focus"), list) else [],
                "strength_themes": canonical_audit.get("strength_themes") if isinstance(canonical_audit.get("strength_themes"), list) else [],
                "objection_themes": canonical_audit.get("objection_themes") if isinstance(canonical_audit.get("objection_themes"), list) else [],
                "cadence": {
                    "news_posts_per_month_min": int((canonical_audit.get("cadence") or {}).get("news_posts_per_month_min") or 4) if isinstance(canonical_audit.get("cadence"), dict) else 4,
                    "photos_per_month_min": int((canonical_audit.get("cadence") or {}).get("photos_per_month_min") or 8) if isinstance(canonical_audit.get("cadence"), dict) else 8,
                    "reviews_response_hours_max": int((canonical_audit.get("cadence") or {}).get("reviews_response_hours_max") or 48) if isinstance(canonical_audit.get("cadence"), dict) else 48,
                },
            },
            "cta": {
                "email": lead_like.get("email") or email,
                "telegram_url": lead_like.get("telegram_url"),
                "whatsapp_url": lead_like.get("whatsapp_url"),
                "website": lead_like.get("website"),
            },
            "updated_at": datetime.utcnow().isoformat(),
        }
        if existing_telegram_notification:
            page_json["telegram_notification"] = existing_telegram_notification

        _send_public_report_ready_telegram(page_json, slug)

        cur.execute(
            """
            UPDATE publicreportrequests
            SET status = %s,
                page_json = %s::jsonb,
                result_json = %s::jsonb,
                error_text = NULL,
                updated_at = NOW()
            WHERE slug = %s
            """,
            (
                "completed",
                json.dumps(page_json, ensure_ascii=False),
                json.dumps(_to_json_compatible(run_result), ensure_ascii=False),
                slug,
            ),
        )
        conn.commit()
    except Exception as e:
        try:
            if conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    UPDATE publicreportrequests
                    SET status = %s,
                        error_text = %s,
                        updated_at = NOW()
                    WHERE slug = %s
                    """,
                    ("error", str(e), slug),
                )
                conn.commit()
        except Exception:
            pass
        print(f"Error running public report pipeline for slug={slug}: {e}")
    finally:
        if conn:
            conn.close()

@app.route('/api/public/report-offer/<slug>', methods=['GET'])
def get_public_report_offer(slug):
    try:
        normalized_slug = _slugify_public_report_name(slug)
        conn = get_db_connection()
        try:
            _ensure_public_report_requests_table(conn)
            cur = conn.cursor()
            cur.execute(
                """
                SELECT slug, status, page_json, error_text, updated_at
                FROM publicreportrequests
                WHERE slug = %s
                LIMIT 1
                """,
                (normalized_slug,),
            )
            row = cur.fetchone()
            if not row:
                return jsonify({"error": "Not found"}), 404
            payload = dict(row) if hasattr(row, "keys") else {
                "slug": row[0],
                "status": row[1],
                "page_json": row[2],
                "error_text": row[3],
                "updated_at": row[4],
            }
            page_json = payload.get("page_json")
            if isinstance(page_json, str):
                try:
                    page_json = json.loads(page_json)
                except Exception:
                    page_json = {}
            if not isinstance(page_json, dict):
                page_json = {}
            page_json["updated_at"] = str(payload.get("updated_at") or page_json.get("updated_at") or "")
            if str(payload.get("status") or "") == "error":
                page_json["processing"] = True
                page_json["processing_message"] = "Отчёт готовится дольше обычного. Мы продолжаем обработку данных."
            return jsonify({"success": True, "status": payload.get("status"), "page": page_json})
        finally:
            conn.close()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """Глобальный обработчик исключений"""
    if isinstance(e, HTTPException):
        if request.path.startswith('/api/'):
            return jsonify({"error": e.description}), e.code
        return e

    logger.exception("Unhandled application error")
    payload = {"error": "Внутренняя ошибка сервера"}
    if getattr(app, "debug", False):
        payload["details"] = str(e)
    return jsonify(payload), 500
