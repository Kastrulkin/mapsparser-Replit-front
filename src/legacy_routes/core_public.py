from legacy_routes import shared as _shared

globals().update(_shared.runtime_namespace)

def _normalize_existing_queue_status(queue_row: Any, default: str = "idle") -> str:
    if not queue_row:
        return default
    status = ""
    if hasattr(queue_row, "get"):
        status = str(queue_row.get("status") or "").strip()
    elif isinstance(queue_row, (list, tuple)) and queue_row:
        status = str(queue_row[0] or "").strip()
    if not status:
        return default
    return normalize_status(status) or default

@app.after_request
def track_agent_discovery_response(response):
    try:
        path = "/" + str(request.path or "").strip().lstrip("/")
        if not should_track_discovery_path(path):
            return response
        db = DatabaseManager()
        cursor = db.conn.cursor()
        log_agent_discovery_event(
            cursor,
            path=path,
            method=str(request.method or "GET"),
            status_code=int(getattr(response, "status_code", 0) or 0),
            user_agent=str(request.headers.get("User-Agent") or ""),
            ip_value=str(request.headers.get("X-Forwarded-For") or request.remote_addr or ""),
            referrer=str(request.headers.get("Referer") or ""),
            metadata={"source": "flask_after_request"},
        )
        db.conn.commit()
        db.close()
    except Exception:
        try:
            db.close()
        except Exception:
            pass
    return response

def competitor_exists(url: str) -> bool:
    try:
        db = DatabaseManager()
        cur = db.conn.cursor()
        cur.execute("SELECT id FROM Cards WHERE url = %s LIMIT 1", (url,))
        row = cur.fetchone()
        db.close()
        return row is not None
    except Exception:
        return False

def save_card_to_db(card: dict) -> None:
    """Сохранить/обновить карточку в локальной БД `Cards`."""
    db = DatabaseManager()
    cur = db.conn.cursor()

    card_id = card.get('id') or str(uuid.uuid4())
    overview = card.get('overview') or {}

    # === АВТОМАТИЧЕСКИЙ АНАЛИЗ ПРИ СОХРАНЕНИИ ===
    try:
        from services.analytics_service import calculate_profile_completeness, generate_seo_recommendations

        # Подготовка данных для анализа
        analysis_data = {
            'phone': (overview or {}).get('phone'),
            'website': (overview or {}).get('site'),
            'schedule': (overview or {}).get('working_hours') or card.get('hours') or card.get('hours_full'),
            'photos_count': card.get('photos_count') or len(card.get('photos', [])),
            'services_count': card.get('services_count') or len(card.get('products', [])),
            'description': (overview or {}).get('description'),
            'messengers': card.get('messengers'),
            'is_verified': card.get('is_verified')
        }

        # Расчет баллов
        seo_score = calculate_profile_completeness(analysis_data)
        recommendations = generate_seo_recommendations(analysis_data)

        # Обновляем объект card перед сохранением
        card['seo_score'] = seo_score
        card['recommendations'] = json.dumps(recommendations, ensure_ascii=False)
        print(f"📊 [save_card_to_db] Auto-Analysis: Score {seo_score}%")

    except Exception as e:
        print(f"⚠️ Warning: Auto-analysis failed in save_card_to_db: {e}")
    # ============================================

    cur.execute(
        """
        INSERT INTO cards (
            id, url, title, address, phone, site, rating, reviews_count,
            categories, overview, products, news, photos, features_full,
            competitors, hours, hours_full, report_path, user_id, seo_score,
            ai_analysis, recommendations
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
            %s::jsonb, %s::jsonb
        )
        ON CONFLICT (id) DO UPDATE SET
            url = EXCLUDED.url,
            title = EXCLUDED.title,
            address = EXCLUDED.address,
            phone = EXCLUDED.phone,
            site = EXCLUDED.site,
            rating = EXCLUDED.rating,
            reviews_count = EXCLUDED.reviews_count,
            categories = EXCLUDED.categories,
            overview = EXCLUDED.overview,
            products = EXCLUDED.products,
            news = EXCLUDED.news,
            photos = EXCLUDED.photos,
            features_full = EXCLUDED.features_full,
            competitors = EXCLUDED.competitors,
            hours = EXCLUDED.hours,
            hours_full = EXCLUDED.hours_full,
            report_path = EXCLUDED.report_path,
            user_id = EXCLUDED.user_id,
            seo_score = EXCLUDED.seo_score,
            ai_analysis = EXCLUDED.ai_analysis,
            recommendations = EXCLUDED.recommendations,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            card_id,
            card.get('url'),
            (overview or {}).get('title'),
            (overview or {}).get('address'),
            (overview or {}).get('phone'),
            (overview or {}).get('site'),
            (overview or {}).get('rating'),
            (overview or {}).get('reviews_count'),
            json.dumps(card.get('categories')),
            json.dumps(card.get('overview')),
            json.dumps(card.get('products')),
            json.dumps(card.get('news')),
            json.dumps(card.get('photos')),
            json.dumps(card.get('features_full')),
            json.dumps(card.get('competitors')),
            json.dumps(card.get('hours')),
            json.dumps(card.get('hours_full')),
            card.get('report_path'),
            card.get('user_id'),
            card.get('seo_score'),
            json.dumps(card.get('ai_analysis'), ensure_ascii=False) if card.get('ai_analysis') is not None else None,
            json.dumps(card.get('recommendations'), ensure_ascii=False) if isinstance(card.get('recommendations'), (dict, list)) else card.get('recommendations'),
        ),
    )
    db.conn.commit()
    db.close()

def _get_client_ip() -> str:
    """
    Определение IP-адреса клиента.
    Учитываем прокси (X-Forwarded-For / X-Real-IP), затем remote_addr.
    """
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        # Берём первый IP из списка
        return x_forwarded_for.split(',')[0].strip()
    real_ip = request.headers.get('X-Real-IP')
    if real_ip:
        return real_ip
    return request.remote_addr or ''

def _detect_country_code() -> str:
    """
    Определяем страну пользователя.
    Сейчас:
    - поддерживаем X-Country-Override для тестов;
    - учитываем DEFAULT_COUNTRY_CODE из .env;
    - TODO: подключить GeoIP по IP-адресу (MaxMind или внешний сервис).
    """
    # Явная переопределяемая страна (для тестов и ручной проверки)
    override = request.headers.get('X-Country-Override')
    if override:
        return override.upper()

    # Значение по умолчанию из окружения (для dev/стейджа)
    env_country = os.getenv('DEFAULT_COUNTRY_CODE')
    if env_country:
        return env_country.upper()

    # На будущее: здесь можно сделать реальный GeoIP по _get_client_ip()
    # ip = _get_client_ip()
    # ...
    return 'US'

def _normalize_content_route(path: str = "") -> str:
    clean_path = str(path or "").strip().split("?", 1)[0].strip("/").rstrip("/\\")
    if not clean_path:
        return "/"
    return f"/{clean_path}"

def _read_frontend_index_html() -> Optional[str]:
    index_path = os.path.join(FRONTEND_DIST_DIR, "index.html")
    try:
        with open(index_path, "r", encoding="utf-8") as file:
            return file.read()
    except OSError as error:
        logger.warning("Could not read frontend index.html for SEO injection: %s", error)
        return None

def _load_content_seo_data() -> Dict[str, Any]:
    seo_path = os.path.join(FRONTEND_DIST_DIR, CONTENT_SEO_FILE)
    try:
        with open(seo_path, "r", encoding="utf-8") as file:
            loaded = json.load(file)
        if isinstance(loaded, dict):
            return loaded
    except OSError as error:
        logger.info("Content SEO file is unavailable: %s", error)
    except json.JSONDecodeError as error:
        logger.warning("Content SEO file is invalid JSON: %s", error)
    return {}

def _escape_head_value(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)

def _route_article_schema(route_path: str, route_seo: Dict[str, Any]) -> List[Dict[str, Any]]:
    article_title = route_seo.get("articleTitle") or route_seo.get("title") or "LocalOS"
    return [
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": article_title,
            "description": route_seo.get("description") or "",
            "datePublished": route_seo.get("publishedAt") or route_seo.get("updatedAt") or "",
            "dateModified": route_seo.get("updatedAt") or route_seo.get("publishedAt") or "",
            "mainEntityOfPage": f"{SITE_URL}{route_path}",
            "author": {
                "@type": "Organization",
                "name": "LocalOS",
            },
            "publisher": {
                "@type": "Organization",
                "name": "LocalOS",
            },
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": 1,
                    "name": "LocalOS",
                    "item": f"{SITE_URL}/",
                },
                {
                    "@type": "ListItem",
                    "position": 2,
                    "name": "Статьи",
                    "item": f"{SITE_URL}/articles",
                },
                {
                    "@type": "ListItem",
                    "position": 3,
                    "name": article_title,
                    "item": f"{SITE_URL}{route_path}",
                },
            ],
        },
    ]

def _schema_for_route(route_path: str, route_seo: Dict[str, Any]) -> Any:
    explicit_schema = route_seo.get("schema")
    if explicit_schema:
        return explicit_schema
    if route_seo.get("ogType") == "article":
        return _route_article_schema(route_path, route_seo)
    return None

def _replace_or_insert_tag(html_text: str, pattern: str, replacement: str) -> str:
    updated, count = re.subn(pattern, replacement, html_text, count=1, flags=re.IGNORECASE | re.DOTALL)
    if count:
        return updated
    return html_text.replace("</head>", f"  {replacement}\n</head>", 1)

def _set_named_meta(html_text: str, attribute: str, key: str, content: str) -> str:
    escaped_content = _escape_head_value(content)
    escaped_key = re.escape(key)
    pattern = rf'<meta\s+{attribute}="{escaped_key}"[^>]*>'
    replacement = f'<meta {attribute}="{key}" content="{escaped_content}" />'
    return _replace_or_insert_tag(html_text, pattern, replacement)

def _set_canonical(html_text: str, url: str) -> str:
    replacement = f'<link rel="canonical" href="{_escape_head_value(url)}" />'
    return _replace_or_insert_tag(html_text, r'<link\s+rel="canonical"[^>]*>', replacement)

def _set_jsonld(html_text: str, schema: Any) -> str:
    if not schema:
        return html_text
    jsonld = json.dumps(schema, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    script = f'<script id="localos-jsonld" type="application/ld+json">{jsonld}</script>'
    updated, count = re.subn(
        r'<script\s+id="localos-jsonld"\s+type="application/ld\+json">.*?</script>',
        script,
        html_text,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if count:
        return updated
    return html_text.replace("</head>", f"  {script}\n</head>", 1)

def _render_spa_index(path: str = ""):
    route_path = _normalize_content_route(path)
    index_html = _read_frontend_index_html()
    if index_html is None:
        return send_from_directory(FRONTEND_DIST_DIR, "index.html")

    seo_data = _load_content_seo_data()
    routes = seo_data.get("routes") if isinstance(seo_data.get("routes"), dict) else {}
    default_seo = seo_data.get("default") if isinstance(seo_data.get("default"), dict) else {}
    route_seo = routes.get(route_path) if isinstance(routes.get(route_path), dict) else default_seo
    title = route_seo.get("title") or default_seo.get("title") or "LocalOS.pro - Локальное продвижение локального бизнеса"
    description = route_seo.get("description") or default_seo.get("description") or ""
    og_type = route_seo.get("ogType") or default_seo.get("ogType") or "website"
    image = seo_data.get("image") or DEFAULT_OG_IMAGE
    canonical_url = f"{SITE_URL}{route_path if route_path != '/' else '/'}"

    index_html = re.sub(
        r"<title>.*?</title>",
        f"<title>{_escape_head_value(title)}</title>",
        index_html,
        count=1,
        flags=re.IGNORECASE | re.DOTALL,
    )
    index_html = _set_named_meta(index_html, "name", "description", description)
    index_html = _set_named_meta(index_html, "property", "og:title", title)
    index_html = _set_named_meta(index_html, "property", "og:description", description)
    index_html = _set_named_meta(index_html, "property", "og:type", og_type)
    index_html = _set_named_meta(index_html, "property", "og:url", canonical_url)
    index_html = _set_named_meta(index_html, "property", "og:image", image)
    index_html = _set_named_meta(index_html, "name", "twitter:image", image)
    index_html = _set_canonical(index_html, canonical_url)
    index_html = _set_jsonld(index_html, _schema_for_route(route_path, route_seo))

    response = Response(index_html, mimetype="text/html")
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.route('/', methods=['GET', 'HEAD', 'OPTIONS', 'POST', 'PUT', 'PATCH', 'DELETE'])
def index():
    """Главная страница - раздаём собранный SPA"""
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        return ('', 405)
    try:
        return _render_spa_index("/")
    except Exception as e:
        # Фолбэк на встроенный шаблон, если сборка отсутствует
        return render_template_string(INDEX_HTML)

@app.route('/assets/<path:filename>')
def serve_assets(filename):
    """Раздача ассетов Vite/SPA"""
    return send_from_directory(os.path.join(FRONTEND_DIST_DIR, 'assets'), filename)

@app.route('/public-audit/<path:filename>')
def serve_public_audit_assets(filename):
    """Раздача ассетов отдельного frontend build для публичных аудитов."""
    return send_from_directory(PUBLIC_FRONTEND_DIST_DIR, filename)

@app.route('/yandex_f5eb229fc5e67c03.html')
def serve_yandex_verification():
    """Yandex Webmaster verification"""
    # Explicitly define root directory to avoid traversal issues
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    return send_from_directory(root_dir, 'yandex_f5eb229fc5e67c03.html')

@app.route('/api/geo/payment-provider', methods=['GET'])
def get_payment_provider():
    """
    Определение платёжного провайдера по стране пользователя.
    - Россия (RU)  -> 'russia'
    - Остальные    -> 'stripe'
    """
    try:
        country = _detect_country_code()
        provider = 'russia' if country == 'RU' else 'stripe'
        return jsonify({
            "success": True,
            "country": country,
            "payment_provider": provider
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

def _normalize_token_usage_category(task_type: Any) -> str:
    task = str(task_type or "").strip().lower()
    if not task:
        return "other"
    if task in {"agent_creation", "agent_builder", "agent_builder_session", "agent_compiler", "agent_blueprint_draft"}:
        return "agent_creation"
    if task in {"operator_chat", "operator_intent_classify", "operator_help", "operator_chat_reply"}:
        return "operator_chat"
    if any(marker in task for marker in ("service", "optimization")):
        return "services_optimization"
    if "news" in task:
        return "news_generation"
    if any(marker in task for marker in ("review", "reply")):
        return "reviews"
    if "agent" in task or "chat" in task:
        return "ai_agents"
    return "other"

@app.route('/api/token-usage', methods=['GET'])
def get_user_token_usage_stats():
    """Получить статистику расхода токенов/кредитов текущего пользователя."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        user_id = user_data.get('user_id') or user_data.get('id')
        if not user_id:
            return jsonify({"error": "Недействительный токен"}), 401

        months = max(1, min(int(request.args.get('months', 1) or 1), 12))
        business_id = str(request.args.get('business_id') or '').strip() or None

        db = DatabaseManager()
        cursor = db.conn.cursor()

        if business_id:
            owner_id = get_business_owner_id(cursor, business_id)
            if not owner_id:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
            if owner_id != user_id and not db.is_superadmin(user_id):
                db.close()
                return jsonify({"error": "Нет доступа"}), 403

        cursor.execute("SELECT to_regclass('public.tokenusage') AS tokenusage_table")
        tokenusage_row = cursor.fetchone()
        tokenusage_exists = bool((_row_to_dict(cursor, tokenusage_row) or {}).get("tokenusage_table"))
        if not tokenusage_exists:
            db.close()
            return jsonify({
                "success": True,
                "period_months": months,
                "month_total": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "requests_count": 0},
                "period_total": {"total_tokens": 0, "prompt_tokens": 0, "completion_tokens": 0, "requests_count": 0},
                "by_category": [],
            })

        now_utc = datetime.now(timezone.utc)
        month_start = now_utc.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        period_start = now_utc - timedelta(days=months * 31)

        filters = ["user_id = %s"]
        params: List[Any] = [user_id]
        if business_id:
            filters.append("business_id = %s")
            params.append(business_id)
        where_sql = " AND ".join(filters)

        def _load_totals(since_dt: datetime) -> Dict[str, int]:
            cursor.execute(
                f"""
                SELECT
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                    COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                    COUNT(*) AS requests_count
                FROM tokenusage
                WHERE {where_sql}
                  AND created_at >= %s
                """,
                [*params, since_dt],
            )
            row = _row_to_dict(cursor, cursor.fetchone()) or {}
            return {
                "total_tokens": int(row.get("total_tokens") or 0),
                "prompt_tokens": int(row.get("prompt_tokens") or 0),
                "completion_tokens": int(row.get("completion_tokens") or 0),
                "requests_count": int(row.get("requests_count") or 0),
            }

        month_total = _load_totals(month_start)
        period_total = _load_totals(period_start)

        cursor.execute(
            f"""
            SELECT
                COALESCE(task_type, 'other') AS task_type,
                COALESCE(SUM(total_tokens), 0) AS total_tokens,
                COALESCE(SUM(prompt_tokens), 0) AS prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) AS completion_tokens,
                COUNT(*) AS requests_count
            FROM tokenusage
            WHERE {where_sql}
              AND created_at >= %s
            GROUP BY COALESCE(task_type, 'other')
            ORDER BY total_tokens DESC
            """,
            [*params, period_start],
        )
        grouped_rows = cursor.fetchall() or []
        grouped: Dict[str, Dict[str, int]] = {}
        for raw_row in grouped_rows:
            row = _row_to_dict(cursor, raw_row) or {}
            category = _normalize_token_usage_category(row.get("task_type"))
            bucket = grouped.setdefault(category, {
                "category": category,
                "total_tokens": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "requests_count": 0,
            })
            bucket["total_tokens"] += int(row.get("total_tokens") or 0)
            bucket["prompt_tokens"] += int(row.get("prompt_tokens") or 0)
            bucket["completion_tokens"] += int(row.get("completion_tokens") or 0)
            bucket["requests_count"] += int(row.get("requests_count") or 0)

        db.close()
        return jsonify({
            "success": True,
            "period_months": months,
            "month_total": month_total,
            "period_total": period_total,
            "by_category": sorted(grouped.values(), key=lambda item: item["total_tokens"], reverse=True),
        })
    except Exception as e:
        print(f"❌ Ошибка получения token usage: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/token-usage', methods=['GET'])
def get_token_usage_stats():
    """Получить статистику использования токенов GigaChat по пользователям и бизнесам (только для суперадмина)"""
    try:
        def _field(row, key, index=None, default=None):
            if row is None:
                return default
            if isinstance(row, dict):
                return row.get(key, default)
            if index is not None and len(row) > index:
                return row[index]
            return default

        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Проверяем, что это суперадмин
        if not user_data.get('is_superadmin'):
            return jsonify({"error": "Доступ запрещён"}), 403

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем, существует ли таблица tokenusage (Postgres)
        cursor.execute("SELECT to_regclass('public.tokenusage') AS table_name")
        tokenusage_row = cursor.fetchone()
        tokenusage_table = None
        if tokenusage_row is not None:
            if isinstance(tokenusage_row, dict):
                tokenusage_table = tokenusage_row.get('table_name')
            else:
                tokenusage_table = tokenusage_row[0]

        if not tokenusage_table:
            db.close()
            return jsonify({
                "success": True,
                "total": {
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "requests_count": 0
                },
                "by_user": [],
                "by_business": [],
                "by_task_type": []
            })

        # Общая статистика
        cursor.execute("""
            SELECT
                SUM(total_tokens) as total,
                SUM(prompt_tokens) as prompt_total,
                SUM(completion_tokens) as completion_total,
                COUNT(*) as requests_count
            FROM TokenUsage
        """)
        total_stats = cursor.fetchone()

        # По пользователям
        cursor.execute("""
            SELECT
                u.id,
                u.email,
                u.name,
                COALESCE(SUM(tu.total_tokens), 0) as total_tokens,
                COALESCE(SUM(tu.prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(tu.completion_tokens), 0) as completion_tokens,
                COUNT(tu.id) as requests_count
            FROM Users u
            LEFT JOIN TokenUsage tu ON u.id = tu.user_id
            GROUP BY u.id, u.email, u.name
            HAVING COALESCE(SUM(tu.total_tokens), 0) > 0
            ORDER BY total_tokens DESC
        """)
        users_stats = []
        for row in cursor.fetchall():
            users_stats.append({
                "user_id": _field(row, "id", 0),
                "email": _field(row, "email", 1),
                "name": _field(row, "name", 2),
                "total_tokens": _field(row, "total_tokens", 3, 0) or 0,
                "prompt_tokens": _field(row, "prompt_tokens", 4, 0) or 0,
                "completion_tokens": _field(row, "completion_tokens", 5, 0) or 0,
                "requests_count": _field(row, "requests_count", 6, 0) or 0
            })

        # По бизнесам
        cursor.execute("""
            SELECT
                b.id,
                b.name,
                b.owner_id,
                u.email as owner_email,
                COALESCE(SUM(tu.total_tokens), 0) as total_tokens,
                COALESCE(SUM(tu.prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(tu.completion_tokens), 0) as completion_tokens,
                COUNT(tu.id) as requests_count
            FROM Businesses b
            LEFT JOIN TokenUsage tu ON b.id = tu.business_id
            LEFT JOIN Users u ON b.owner_id = u.id
            GROUP BY b.id, b.name, b.owner_id, u.email
            HAVING COALESCE(SUM(tu.total_tokens), 0) > 0
            ORDER BY total_tokens DESC
        """)
        businesses_stats = []
        for row in cursor.fetchall():
            businesses_stats.append({
                "business_id": _field(row, "id", 0),
                "business_name": _field(row, "name", 1),
                "owner_id": _field(row, "owner_id", 2),
                "owner_email": _field(row, "owner_email", 3),
                "total_tokens": _field(row, "total_tokens", 4, 0) or 0,
                "prompt_tokens": _field(row, "prompt_tokens", 5, 0) or 0,
                "completion_tokens": _field(row, "completion_tokens", 6, 0) or 0,
                "requests_count": _field(row, "requests_count", 7, 0) or 0
            })

        # По типам задач
        cursor.execute("""
            SELECT
                task_type,
                COALESCE(SUM(total_tokens), 0) as total_tokens,
                COALESCE(SUM(prompt_tokens), 0) as prompt_tokens,
                COALESCE(SUM(completion_tokens), 0) as completion_tokens,
                COUNT(*) as requests_count
            FROM TokenUsage
            GROUP BY task_type
            ORDER BY total_tokens DESC
        """)
        task_types_stats = []
        for row in cursor.fetchall():
            task_types_stats.append({
                "task_type": _field(row, "task_type", 0, "unknown") or "unknown",
                "total_tokens": _field(row, "total_tokens", 1, 0) or 0,
                "prompt_tokens": _field(row, "prompt_tokens", 2, 0) or 0,
                "completion_tokens": _field(row, "completion_tokens", 3, 0) or 0,
                "requests_count": _field(row, "requests_count", 4, 0) or 0
            })

        db.close()

        return jsonify({
            "success": True,
            "total": {
                "total_tokens": _field(total_stats, "total", 0, 0) or 0,
                "prompt_tokens": _field(total_stats, "prompt_total", 1, 0) or 0,
                "completion_tokens": _field(total_stats, "completion_total", 2, 0) or 0,
                "requests_count": _field(total_stats, "requests_count", 3, 0) or 0
            },
            "by_user": users_stats,
            "by_business": businesses_stats,
            "by_task_type": task_types_stats
        })

    except Exception as e:
        print(f"❌ Ошибка получения статистики токенов: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def _count_from_row(cursor, row):
    """Безопасно извлечь число из строки SELECT COUNT(*) AS cnt: tuple или RealDictRow."""
    if row is None:
        return 0
    rd = _row_to_dict(cursor, row)
    if not rd:
        return 0
    if "cnt" in rd and rd["cnt"] is not None:
        return int(rd["cnt"])
    return int(list(rd.values())[0]) if rd else 0

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(FRONTEND_DIST_DIR, 'favicon.ico')

@app.route('/favicon.svg')
def favicon_svg():
    return send_from_directory(FRONTEND_DIST_DIR, 'favicon.svg')

@app.route('/robots.txt')
def robots():
    return send_from_directory(FRONTEND_DIST_DIR, 'robots.txt')

def _require_superadmin(user_data, db):
    if not user_data:
        return False
    try:
        return db.is_superadmin(user_data["user_id"])
    except Exception:
        return False

def _load_userbot_or_error(db, business_id: str | None):
    cursor = db.conn.cursor()
    auth_data = load_userbot_account(cursor, business_id=business_id)
    if not auth_data:
        return None, {"error": "Telegram app не настроен", "code": "telegram_app_missing"}, 400
    api_id = int(auth_data.get("api_id") or 0)
    api_hash = str(auth_data.get("api_hash") or "").strip()
    phone = str(auth_data.get("phone") or "").strip()
    if not api_id or not api_hash or not phone:
        return None, {"error": "Telegram app: api_id/api_hash/phone не заданы", "code": "telegram_app_incomplete"}, 400
    return auth_data, None, None

@app.route("/api/admin/businesses/<business_id>/card-automation", methods=["GET", "PUT", "OPTIONS"])
def admin_business_card_automation(business_id: str):
    try:
        if request.method == "OPTIONS":
            return ("", 204)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        if not _require_superadmin(user_data, db):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        ensure_card_automation_tables(db.conn)
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM businesses WHERE id = %s LIMIT 1", (business_id,))
        exists = cursor.fetchone()
        if not exists:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if request.method == "GET":
            snapshot = get_card_automation_snapshot(db.conn, business_id)
            db.close()
            return jsonify({"success": True, **snapshot})

        payload = request.get_json(silent=True) or {}
        snapshot = save_card_automation_settings(db.conn, business_id, user_data["user_id"], payload)
        db.close()
        return jsonify({"success": True, **snapshot})
    except Exception as e:
        print(f"❌ Ошибка card automation settings: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/businesses/<business_id>/card-automation/run", methods=["POST", "OPTIONS"])
def admin_run_business_card_automation(business_id: str):
    try:
        if request.method == "OPTIONS":
            return ("", 204)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        if not _require_superadmin(user_data, db):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        ensure_card_automation_tables(db.conn)
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM businesses WHERE id = %s LIMIT 1", (business_id,))
        exists = cursor.fetchone()
        if not exists:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        payload = request.get_json(silent=True) or {}
        action_type = str(payload.get("action_type") or "").strip().lower()
        result = run_card_automation_action(
            db.conn,
            business_id=business_id,
            action_type=action_type,
            triggered_by="superadmin",
        )
        snapshot = get_card_automation_snapshot(db.conn, business_id)
        db.close()
        return jsonify({"success": True, "result": result, **snapshot})
    except Exception as e:
        print(f"❌ Ошибка ручного запуска card automation: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/admin/telegram-userbot/status", methods=["GET"])
def telegram_userbot_status():
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        if not _require_superadmin(user_data, db):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        business_id = request.args.get("business_id") or None
        auth_data = load_userbot_account(db.conn.cursor(), business_id=business_id)
        if not auth_data:
            db.close()
            return jsonify({"configured": False, "authorized": False}), 200

        session_string = str(auth_data.get("session_string") or "").strip()
        db.close()
        return jsonify({
            "configured": True,
            "authorized": bool(session_string),
            "phone": auth_data.get("phone"),
        })

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ Ошибка telegram-userbot/status: {e}\n{err_tb}")
        payload = {"error": str(e), "detail": "telegram_userbot_status"}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@app.route("/api/admin/telegram-userbot/request-code", methods=["POST"])
def telegram_userbot_request_code():
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json() or {}
        business_id = data.get("business_id") or None

        db = DatabaseManager()
        if not _require_superadmin(user_data, db):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        auth_data, err_payload, err_status = _load_userbot_or_error(db, business_id)
        if not auth_data:
            db.close()
            return jsonify(err_payload), err_status

        result = userbot_send_code(auth_data)
        db.close()
        return jsonify({"success": True, "result": result})

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ Ошибка telegram-userbot/request-code: {e}\n{err_tb}")
        payload = {"error": str(e), "detail": "telegram_userbot_request_code"}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@app.route("/api/admin/telegram-userbot/confirm-code", methods=["POST"])
def telegram_userbot_confirm_code():
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json() or {}
        code = str(data.get("code") or "").strip()
        if not code:
            return jsonify({"error": "code обязателен"}), 400
        business_id = data.get("business_id") or None

        db = DatabaseManager()
        if not _require_superadmin(user_data, db):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        auth_data, err_payload, err_status = _load_userbot_or_error(db, business_id)
        if not auth_data:
            db.close()
            return jsonify(err_payload), err_status

        result = userbot_confirm_code(auth_data, code)
        session_string = result.get("session_string")
        account_id = auth_data.get("account_id")
        if session_string and account_id:
            auth_data["session_string"] = session_string
            update_userbot_session(db.conn.cursor(), account_id, auth_data)
            db.conn.commit()
        db.close()
        return jsonify({"success": True, "result": result})

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ Ошибка telegram-userbot/confirm-code: {e}\n{err_tb}")
        payload = {"error": str(e), "detail": "telegram_userbot_confirm_code"}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@app.route("/api/admin/telegram-userbot/send", methods=["POST"])
def telegram_userbot_send():
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401
        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json() or {}
        phone = str(data.get("phone") or "").strip()
        message = str(data.get("message") or "").strip()
        if not phone or not message:
            return jsonify({"error": "phone и message обязательны"}), 400
        business_id = data.get("business_id") or None

        db = DatabaseManager()
        if not _require_superadmin(user_data, db):
            db.close()
            return jsonify({"error": "Нет доступа"}), 403

        auth_data, err_payload, err_status = _load_userbot_or_error(db, business_id)
        if not auth_data:
            db.close()
            return jsonify(err_payload), err_status

        result = userbot_send_message(auth_data, phone, message)
        status = result.get("status")
        db.close()
        if status == "not_authorized":
            return jsonify({"error": "Telegram app не авторизован", "code": "telegram_app_not_authorized"}), 409
        return jsonify({"success": True, "result": result})

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ Ошибка telegram-userbot/send: {e}\n{err_tb}")
        payload = {"error": str(e), "detail": "telegram_userbot_send"}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@app.route("/api/business/<business_id>/competitors/manual", methods=["GET"])
def get_manual_competitors(business_id):
    """Возвращает конкурентов из последнего card snapshot (ручной блок UI)."""
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404
        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        cursor.execute(
            """
            SELECT competitors
            FROM cards
            WHERE business_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (business_id,),
        )
        row = cursor.fetchone()
        db.close()

        competitors_raw = (_row_to_dict(cursor, row) or {}).get("competitors") if row else None
        competitors = []
        if isinstance(competitors_raw, list):
            competitors = competitors_raw
        elif isinstance(competitors_raw, str):
            try:
                parsed = json.loads(competitors_raw)
                competitors = parsed if isinstance(parsed, list) else []
            except Exception:
                competitors = []

        return jsonify({"success": True, "competitors": competitors, "count": len(competitors)})
    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_manual_competitors: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_manual_competitors", "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@app.route("/api/business/<business_id>/services", methods=["GET"])
def get_business_services(business_id):
    """
    Получить список услуг бизнеса
    """
    try:
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(" ")[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверка доступа
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data["user_id"] and not db.is_superadmin(user_data["user_id"]):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Читаем из userservices (Postgres, каноничная таблица услуг)
        cursor.execute("""
            SELECT id, category, name, description, price, price_from, price_to, created_at
            FROM userservices
            WHERE business_id = %s AND (is_active IS TRUE OR is_active IS NULL)
            ORDER BY category NULLS LAST, name NULLS LAST, created_at DESC
        """, (business_id,))
        rows = cursor.fetchall()
        db.close()

        services = []
        for r in rows:
            rd = _row_to_dict(cursor, r)
            if not rd:
                continue
            price = rd.get("price")
            if price is None and (rd.get("price_from") is not None or rd.get("price_to") is not None):
                price = str(rd.get("price_from") or "") if rd.get("price_from") == rd.get("price_to") else f"{rd.get('price_from') or ''}-{rd.get('price_to') or ''}"
            services.append({
                "id": rd.get("id"),
                "category": rd.get("category") or "Без категории",
                "name": rd.get("name") or "",
                "description": rd.get("description") or "",
                "price": price,
                "created_at": rd.get("created_at"),
            })

        return jsonify({"success": True, "services": services})

    except Exception as e:
        import traceback
        err_tb = traceback.format_exc()
        print(f"❌ get_business_services: {e}\n{err_tb}")
        payload = {"success": False, "where": "get_business_services", "error": str(e)}
        if getattr(app, "debug", False):
            payload["traceback"] = err_tb
        return jsonify(payload), 500

@app.route('/api/superadmin/users/<user_id>', methods=['DELETE'])
def delete_user(user_id):
    """Удалить пользователя - только для суперадмина"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403

        # Нельзя удалить самого себя
        if user_id == user_data['user_id']:
            db.close()
            return jsonify({"error": "Нельзя удалить самого себя"}), 400

        # Проверяем, что пользователь существует
        cursor = db.conn.cursor()
        cursor.execute("SELECT id, email FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            db.close()
            return jsonify({"error": "Пользователь не найден"}), 404

        # Удаляем пользователя (каскадное удаление удалит все связанные данные)
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

        db.conn.commit()
        db.close()

        return jsonify({"success": True, "message": "Пользователь удален"})

    except Exception as e:
        print(f"❌ Ошибка удаления пользователя: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/superadmin/users/<user_id>/pause', methods=['POST'])
def pause_user(user_id):
    """Приостановить пользователя (деактивировать) - только для суперадмина"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403

        # Проверяем, что пользователь существует
        cursor = db.conn.cursor()
        cursor.execute("SELECT id, email, is_active FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            db.close()
            return jsonify({"error": "Пользователь не найден"}), 404

        # Нельзя деактивировать самого себя
        if user_id == user_data['user_id']:
            db.close()
            return jsonify({"error": "Нельзя деактивировать самого себя"}), 400

        # Деактивируем пользователя
        cursor.execute("""
            UPDATE Users
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (user_id,))

        # Деактивируем все бизнесы пользователя
        cursor.execute("""
            UPDATE Businesses
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE owner_id = %s
        """, (user_id,))

        db.conn.commit()
        db.close()

        return jsonify({"success": True, "message": "Пользователь приостановлен"})

    except Exception as e:
        print(f"❌ Ошибка приостановки пользователя: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/superadmin/users/<user_id>/unpause', methods=['POST'])
def unpause_user(user_id):
    """Возобновить пользователя (активировать) - только для суперадмина"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Проверяем права суперадмина
        db = DatabaseManager()
        if not db.is_superadmin(user_data['user_id']):
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403

        # Проверяем, что пользователь существует
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM users WHERE id = %s", (user_id,))
        user = cursor.fetchone()

        if not user:
            db.close()
            return jsonify({"error": "Пользователь не найден"}), 404

        # Активируем пользователя
        cursor.execute("""
            UPDATE Users
            SET is_active = 1, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        """, (user_id,))

        # Активируем все бизнесы пользователя
        cursor.execute("""
            UPDATE Businesses
            SET is_active = 1, updated_at = CURRENT_TIMESTAMP
            WHERE owner_id = %s
        """, (user_id,))

        db.conn.commit()
        db.close()

        return jsonify({"success": True, "message": "Пользователь возобновлен"})

    except Exception as e:
        print(f"❌ Ошибка возобновления пользователя: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/superadmin/users/<user_id>/send-password-setup', methods=['POST'])
@rate_limit_if_available("20 per hour")
def send_user_password_setup(user_id):
    """Отправить безопасную ссылку установки пароля passwordless-пользователю."""
    try:
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        db = DatabaseManager()
        try:
            if not db.is_superadmin(user_data['user_id']):
                return jsonify({"error": "Недостаточно прав"}), 403
        finally:
            db.close()

        from auth_system import create_password_setup_token

        result = create_password_setup_token(user_id)
        if result.get("error"):
            return jsonify({"error": result["error"]}), 400

        setup_url = build_password_setup_link(result["email"], result["verification_token"])
        email_sent = send_password_setup_email(
            result["email"],
            result.get("name"),
            result["verification_token"],
        )

        return jsonify(
            {
                "success": True,
                "email_sent": bool(email_sent),
                "setup_url": setup_url,
                "email": result["email"],
                "message": "Ссылка установки пароля сформирована",
            }
        )
    except Exception as e:
        print(f"❌ Ошибка отправки ссылки установки пароля: {e}")
        return jsonify({"error": str(e)}), 500

def _is_sensitive_probe_path(path: str) -> bool:
    normalized = str(path or "").strip().lower().lstrip("/")
    if not normalized:
        return False
    if normalized in SENSITIVE_PROBE_EXACT_PATHS:
        return True
    return any(marker in normalized for marker in SENSITIVE_PROBE_PATH_MARKERS)

@app.route('/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS', 'PATCH'])
def spa_fallback(path):
    # Не трогаем API маршруты
    if path.startswith('api/'):
        # Для несуществующих API путей отвечаем корректным JSON и статусами, а не HTML/405
        if request.method == 'OPTIONS':
            return ('', 204)
        return jsonify({"error": "Not Found"}), 404

    if _is_sensitive_probe_path(path):
        return jsonify({"error": "Not Found"}), 404

    if path.startswith('public-audit/'):
        public_full_path = os.path.join(PUBLIC_FRONTEND_DIST_DIR, path.removeprefix('public-audit/'))
        if os.path.isfile(public_full_path):
            return send_from_directory(PUBLIC_FRONTEND_DIST_DIR, path.removeprefix('public-audit/'))
        return jsonify({"error": "Not Found"}), 404

    full_path = os.path.join(FRONTEND_DIST_DIR, path)
    if os.path.isfile(full_path):
        # Если файл существует в dist, отдаем его напрямую
        return send_from_directory(FRONTEND_DIST_DIR, path)

    if _is_public_offer_slug(path):
        response = send_from_directory(os.path.join(PUBLIC_FRONTEND_DIST_DIR, 'public-audit'), 'index.html')
        if response:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response

    # Иначе - SPA индекс с route-specific SEO/JSON-LD для краулеров без JavaScript.
    return _render_spa_index(path)

@app.route('/api/users/reports', methods=['GET'])
def stub_users_reports():
    return jsonify({"success": True, "reports": []})

@app.route('/api/users/queue', methods=['GET'])
def stub_users_queue():
    return jsonify({"success": True, "queue": []})

@app.route('/api/analyze', methods=['POST'])
@rate_limit_if_available("20 per hour")
def analyze():
    """API для анализа карточки"""
    try:
        data = request.get_json()
        url = data.get('url', '').strip()

        if not url:
            return jsonify({"success": False, "error": "URL не предоставлен"})

        print(f"Анализируем карточку: {url}")
        card_data = parse_yandex_card(url)

        # Проверка на капчу
        if card_data.get('error') == 'captcha_detected':
            return jsonify({
                "success": False,
                "error": "Страница закрыта капчой. Попробуйте позже или пройдите капчу вручную."
            })

        # Логика выбора и парсинга конкурента
        competitor_data = None
        competitor_url = None
        competitors = card_data.get('competitors', [])
        competitor_status = ''

        if competitors:
            for comp in competitors:
                comp_url = comp.get('url')
                if comp_url and not competitor_exists(comp_url):
                    competitor_url = comp_url
                    break
            if competitor_url:
                print(f"Парсим конкурента: {competitor_url}")
                try:
                    competitor_data = parse_yandex_card(competitor_url)
                    competitor_data['competitors'] = []
                    save_card_to_db(competitor_data)
                except Exception as e:
                    print(f"Ошибка при парсинге конкурента: {e}")
                    competitor_status = f"Ошибка при парсинге конкурента: {e}"
            else:
                competitor_status = "Все конкуренты уже были спарсены ранее."
        else:
            competitor_status = "Конкуренты не найдены на карточке."

        # Сохраняем основную карточку
        competitors_urls = []
        if competitor_url:
            competitors_urls.append(competitor_url)
        card_data['competitors'] = competitors_urls
        save_card_to_db(card_data)

        # Анализ и генерация отчёта
        print("Анализ данных...")
        analysis = analyze_card(card_data)
        print("Генерация отчёта...")
        report_path = generate_html_report(
            card_data,
            analysis,
            competitor_data if competitor_data else {'status': competitor_status}
        )

        return jsonify({
            "success": True,
            "title": card_data.get('overview', {}).get('title', 'Без названия'),
            "seo_score": analysis.get('score', 0),
            "card_id": card_data.get('id', 'unknown'),
            "report_path": report_path
        })

    except Exception as e:
        print(f"Ошибка при анализе: {e}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/health', methods=['GET'])
def health():
    """Проверка здоровья сервера"""
    return jsonify({"status": "ok", "message": "SEO анализатор работает"})

def _row_to_dict(cursor, row):
    """Маппинг строки в dict: dict-like row — по ключам, tuple-row — по cursor.description."""
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {k: row[k] for k in row.keys()}
    cols = [d[0] for d in cursor.description]
    return dict(zip(cols, row))

def _table_columns(cursor, table_name: str) -> set:
    """Получить набор колонок (lowercase) для таблицы Postgres."""
    cursor.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        """,
        (table_name.lower(),),
    )
    cols = set()
    for row in cursor.fetchall() or []:
        if hasattr(row, "get"):
            name = row.get("column_name")
        else:
            name = row[0] if row else None
        if name:
            cols.add(str(name).lower())
    return cols

def _resolve_network_scope_for_business(cursor, business_id, requested_scope):
    cursor.execute(
        """
        SELECT id, name, address, network_id
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    raw_business = cursor.fetchone()
    business_row = _row_to_dict(cursor, raw_business) if raw_business else None
    network_id = business_row.get("network_id") if business_row else None
    network_id_value = str(network_id or "").strip()
    if not network_id_value:
        cursor.execute("SELECT id FROM networks WHERE id = %s LIMIT 1", (business_id,))
        raw_network = cursor.fetchone()
        network_row = _row_to_dict(cursor, raw_network) if raw_network else None
        network_id_value = str((network_row or {}).get("id") or "").strip()
    # Parent network business is represented as a business row whose id equals network_id.
    # The UI often calls ordinary business endpoints without scope=network, so parent rows
    # must aggregate child locations by default.
    aggregate_network = bool(network_id_value) and (
        requested_scope == "network" or str(business_id or "").strip() == network_id_value
    )
    return business_row, network_id_value or None, aggregate_network

def _network_business_filter(column_name):
    return f"({column_name} IN (SELECT id FROM businesses WHERE network_id = %s) OR {column_name} = %s)"

def _resolve_request_business_id(user_data, *, json_data=None):
    """Извлечь business_id из query/form/json, чтобы не падать на fallback к "первому бизнесу"."""
    payload = json_data if isinstance(json_data, dict) else {}
    candidates = [
        request.args.get('business_id'),
        request.form.get('business_id'),
        payload.get('business_id'),
        payload.get('businessId'),
    ]
    for candidate in candidates:
        normalized = str(candidate or "").strip()
        if not normalized:
            continue
        try:
            db = DatabaseManager()
            cursor = db.conn.cursor()
            owner_id = get_business_owner_id(cursor, normalized, include_active_check=False)
            db.close()
            if owner_id and (owner_id == user_data.get('user_id') or user_data.get('is_superadmin')):
                return normalized
        except Exception as access_exc:
            print(f"⚠️ _resolve_request_business_id access check skipped: {access_exc}")
            return normalized

    return get_business_id_from_user(user_data['user_id'], None)

def _business_display_fields(row_dict):
    """Из row_dict (из businesses) извлечь поля для UI: name, business_type, address, working_hours (строки)."""
    if not row_dict:
        return "", "", "", ""
    def s(v):
        return (v or "").strip() if v is not None else ""
    return s(row_dict.get("name")), s(row_dict.get("business_type")), s(row_dict.get("address")), s(row_dict.get("working_hours"))

def suggest_city_from_address(address: str):
    """Подсказка города из адреса (best-effort, без справочника). Не перезаписывает введённый пользователем city."""
    if not address or not isinstance(address, str):
        return None
    addr = address.strip()
    if not addr:
        return None
    # Первый кандидат — до первой запятой
    if "," in addr:
        candidate = addr.split(",")[0].strip()
    else:
        candidate = addr
    if not candidate:
        return None
    # Убираем префиксы: г. / город / city
    for prefix in ("г.", "город", "city", "Г.", "Город", "City"):
        if candidate.lower().startswith(prefix.lower()):
            candidate = candidate[len(prefix):].strip()
            break
    return candidate if candidate else None

def parse_ll_from_maps_url(maps_url: str):
    """Из ссылки на карты (yandex и т.п.) извлечь ll=lon,lat. Возвращает (geo_lon, geo_lat) или (None, None)."""
    if not maps_url or "ll=" not in maps_url:
        return None, None
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(maps_url)
        qs = parse_qs(parsed.query)
        ll = qs.get("ll") or qs.get("LL")
        if not ll or not ll[0]:
            return None, None
        parts = ll[0].strip().split(",")
        if len(parts) != 2:
            return None, None
        lon_f = float(parts[0].strip())
        lat_f = float(parts[1].strip())
        return lon_f, lat_f
    except (ValueError, IndexError, TypeError):
        return None, None

def _table_has_column(cursor, table_name: str, column_name: str) -> bool:
    table = str(table_name or "").strip().lower()
    column = str(column_name or "").strip().lower()
    if not table or not column:
        return False
    try:
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND lower(table_name) = %s
              AND lower(column_name) = %s
            LIMIT 1
            """,
            (table, column),
        )
        return bool(cursor.fetchone())
    except Exception:
        return False

def _normalize_geocoding_address(address: str) -> str:
    text = str(address or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    country_markers = ("россия", "russia", "russian federation")
    if any(marker in lowered for marker in country_markers):
        return text
    if re.search(r"[а-яё]", lowered):
        return f"{text}, Россия"
    return text

@lru_cache(maxsize=1024)
def _geocode_address(address: str) -> tuple[Optional[float], Optional[float]]:
    query = _normalize_geocoding_address(address)
    if not query:
        return None, None
    try:
        response = requests.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": query,
                "format": "jsonv2",
                "limit": 1,
            },
            headers={
                "User-Agent": "LocalOS/1.0 (support@localos.pro)",
                "Accept-Language": "ru",
            },
            timeout=8,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload:
            return None, None
        first_item = payload[0] or {}
        lat = float(first_item.get("lat"))
        lon = float(first_item.get("lon"))
        return lat, lon
    except Exception as exc:
        print(f"⚠️ geocode address failed for '{query}': {exc}")
        return None, None

def _resolve_business_coordinates(
    cursor,
    business_id: str,
    address: str,
    geo_lat: Any,
    geo_lon: Any,
    *,
    allow_external_lookup: bool = False,
) -> tuple[Any, Any]:
    raw_lat = str(geo_lat or "").strip().replace(",", ".")
    raw_lon = str(geo_lon or "").strip().replace(",", ".")
    try:
        lat_value = float(raw_lat)
        lon_value = float(raw_lon)
        if lat_value and lon_value:
            return lat_value, lon_value
    except (TypeError, ValueError):
        pass

    resolved_lat = None
    resolved_lon = None
    try:
        cursor.execute(
            """
            SELECT url
            FROM businessmaplinks
            WHERE business_id = %s
            ORDER BY created_at DESC
            """,
            (business_id,),
        )
        for row in cursor.fetchall() or []:
            row_url = row["url"] if hasattr(row, "keys") else row[0]
            map_lon, map_lat = parse_ll_from_maps_url(str(row_url or ""))
            if map_lat is not None and map_lon is not None:
                resolved_lat = map_lat
                resolved_lon = map_lon
                break
    except Exception as exc:
        print(f"⚠️ map link coordinate lookup failed for business {business_id}: {exc}")

    if (resolved_lat is None or resolved_lon is None) and allow_external_lookup:
        resolved_lat, resolved_lon = _geocode_address(address)

    if resolved_lat is None or resolved_lon is None:
        return geo_lat, geo_lon

    try:
        cursor.execute(
            """
            UPDATE businesses
            SET geo_lat = %s,
                geo_lon = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (resolved_lat, resolved_lon, business_id),
        )
    except Exception as exc:
        print(f"⚠️ business coordinate update failed for {business_id}: {exc}")

    return resolved_lat, resolved_lon

def get_user_language(user_id: str, requested_language: str = None) -> str:
    """
    Получить язык пользователя из профиля бизнеса или использовать запрошенный язык.

    Args:
        user_id: ID пользователя
        requested_language: Язык, указанный в запросе (если есть)

    Returns:
        Код языка (ru, en, es, de, fr, it, pt, zh)
    """
    # Если язык указан в запросе - используем его
    if requested_language:
        return requested_language.lower()

    # Иначе получаем язык из профиля бизнеса пользователя
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        # Получаем первый активный бизнес пользователя
        cursor.execute("""
            SELECT ai_agent_language
            FROM businesses
            WHERE owner_id = %s AND (is_active = TRUE OR is_active IS NULL)
            ORDER BY created_at DESC
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()
        db.close()

        if row:
            language_value = None
            if isinstance(row, dict):
                language_value = row.get("ai_agent_language")
            else:
                language_value = row[0] if len(row) > 0 else None
            if language_value:
                return str(language_value).lower()
    except Exception as e:
        print(f"⚠️ Ошибка получения языка пользователя: {e}")

    # Fallback на русский, если ничего не найдено
    return 'ru'

def _normalize_text_for_semantic_compare(value: str) -> str:
    """Нормализует строку для сравнения «по смыслу» (без регистра/пунктуации/лишних пробелов)."""
    import re as _re
    if value is None:
        return ""
    text = str(value).strip().lower().replace("ё", "е")
    text = _re.sub(r"[^\w\sа-яА-Я]", " ", text, flags=_re.UNICODE)
    text = _re.sub(r"\s+", " ", text, flags=_re.UNICODE).strip()
    return text

def _format_template_with_literal_json_fallback(template: str, values: dict[str, object]) -> str:
    try:
        return template.format(**values)
    except (KeyError, ValueError, TypeError):
        result = str(template or "")
        for key, value in values.items():
            result = result.replace("{" + key + "}", str(value or ""))
        return result

def _strip_model_markup(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^\s*```(?:json|JSON)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    text = text.strip()
    return text.strip(" \n\r\t`")

def _extract_review_reply_from_model_result(result: object) -> tuple[str, bool]:
    if result is None:
        return "", True
    if isinstance(result, dict):
        if result.get("error"):
            return "", True
        return _strip_model_markup(result.get("reply") or ""), False

    text = _strip_model_markup(result)
    if not text:
        return "", True

    json_start = text.find("{")
    json_end = text.rfind("}") + 1
    if json_start != -1 and json_end > json_start:
        json_str = text[json_start:json_end]
        try:
            parsed = json.loads(json_str)
            if isinstance(parsed, dict):
                if parsed.get("error"):
                    return "", True
                return _strip_model_markup(parsed.get("reply") or ""), False
        except json.JSONDecodeError:
            match = re.search(r'"reply"\s*:\s*"((?:\\.|[^"\\])*)"', json_str, flags=re.DOTALL)
            if match:
                try:
                    return _strip_model_markup(json.loads('"' + match.group(1) + '"')), True
                except json.JSONDecodeError:
                    return _strip_model_markup(match.group(1)), True
            return _strip_model_markup(text), True

    return text, False

def _review_reply_detail_phrase(review_text: object) -> str:
    normalized = _normalize_text_for_semantic_compare(str(review_text or ""))
    details: list[str] = []
    if "аккурат" in normalized:
        details.append("аккуратность мастера")
    if "удоб" in normalized and "запис" in normalized:
        details.append("удобство записи")
    if "внимател" in normalized:
        details.append("внимательное отношение")
    if "быстр" in normalized:
        details.append("быструю работу")
    if "чист" in normalized:
        details.append("чистоту")
    if "грум" in normalized and not details:
        details.append("качество груминга")
    if not details:
        return ""
    if len(details) == 1:
        return details[0]
    return ", ".join(details[:-1]) + " и " + details[-1]
