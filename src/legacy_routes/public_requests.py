from legacy_routes import shared as _shared

globals().update(_shared.runtime_namespace)

@app.route('/api/admin/prompts/learning-candidates', methods=['GET', 'OPTIONS'])
def get_prompt_learning_candidates():
    """Показать суперадмину human-review кандидаты для улучшения общих промптов."""
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
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403

        try:
            days = int(request.args.get("days") or 30)
        except Exception:
            days = 30
        try:
            limit = int(request.args.get("limit") or 12)
        except Exception:
            limit = 12

        items = get_service_optimization_learning_candidates(db.conn, days=days, limit=limit)
        db.close()
        return jsonify({
            "success": True,
            "window_days": max(1, min(days, 180)),
            "items": items,
            "policy": {
                "auto_apply": False,
                "reviewer": "superadmin",
                "note": "Кандидаты не меняют общие промпты автоматически. Суперадмин должен вручную утвердить и внести правило в промпт.",
            },
        })
    except Exception as e:
        print(f"❌ Ошибка получения learning candidates: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/industry-patterns/recalibrate', methods=['POST', 'OPTIONS'])
def run_industry_patterns_recalibration():
    """Создать pending предложения по monthly recalibration. Без автоприменения."""
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
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403

        result = run_monthly_industry_pattern_recalibration(db.conn, create_proposals=True)
        db.close()
        return jsonify({
            "success": True,
            "auto_apply": False,
            "result": result,
        })
    except Exception as e:
        print(f"❌ Ошибка monthly industry recalibration: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/industry-patterns/proposals', methods=['GET', 'OPTIONS'])
def list_industry_pattern_proposals():
    """Список предложений паттернов для human-in-the-loop review."""
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
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403

        ensure_industry_pattern_tables(db.conn)
        status = str(request.args.get("status") or "pending_review").strip()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT id, industry_key, pattern_type, proposed_pattern, examples_json,
                   source_period_start, source_period_end, source_counts_json,
                   confidence, risk_level, status, reviewed_by, reviewed_at,
                   decision_comment, activated_version_id, created_at, updated_at
            FROM industry_pattern_proposals
            WHERE status = %s
            ORDER BY created_at DESC
            LIMIT 100
            """,
            (status,),
        )
        items = []
        for row in cursor.fetchall() or []:
            row_data = _row_to_dict(cursor, row) if row else {}
            items.append(row_data)
        db.close()
        return jsonify({"success": True, "status": status, "items": items})
    except Exception as e:
        print(f"❌ Ошибка списка industry pattern proposals: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/industry-patterns/proposals/<proposal_id>/decision', methods=['POST', 'OPTIONS'])
def decide_industry_pattern(proposal_id):
    """Принять, отклонить или отправить на доработку proposed pattern."""
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
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403

        data = request.get_json(silent=True) or {}
        result = decide_industry_pattern_proposal(
            db.conn,
            proposal_id=proposal_id,
            decision=str(data.get("decision") or ""),
            decided_by=str(user_data['user_id']),
            decision_comment=str(data.get("comment") or ""),
        )
        db.close()
        return jsonify({"success": True, "result": result})
    except Exception as e:
        print(f"❌ Ошибка решения industry pattern proposal: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/prompts/<prompt_type>', methods=['PUT', 'OPTIONS'])
def update_prompt(prompt_type):
    """Обновить промпт (только для суперадмина)"""
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

        data = request.get_json()
        prompt_text = data.get('text', '').strip()
        description = data.get('description', '').strip()

        if not prompt_text:
            return jsonify({"error": "Текст промпта не может быть пустым"}), 400

        cursor = db.conn.cursor()
        cursor.execute("""
            UPDATE aiprompts
            SET prompt_text = %s, description = %s, updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE prompt_type = %s
        """, (prompt_text, description, user_data['user_id'], prompt_type))

        if cursor.rowcount == 0:
            # Если промпта нет, создаём его
            cursor.execute("""
                INSERT INTO aiprompts (id, prompt_type, prompt_text, description, updated_by)
                VALUES (%s, %s, %s, %s, %s)
            """, (f"prompt_{prompt_type}", prompt_type, prompt_text, description, user_data['user_id']))

        db.conn.commit()
        db.close()

        return jsonify({"success": True})

    except Exception as e:
        print(f"❌ Ошибка обновления промпта: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def get_prompt_from_db(prompt_type: str, fallback: str = None) -> str:
    """Получить промпт из БД или использовать fallback"""
    try:
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("SELECT prompt_text FROM aiprompts WHERE prompt_type = %s", (prompt_type,))
        row = cursor.fetchone()
        db.close()

        if row:
            # Правильно извлекаем строку из row (может быть tuple, dict, или sqlite3.Row)
            prompt_text = None

            # Если это sqlite3.Row (имеет атрибут keys)
            if hasattr(row, 'keys'):
                try:
                    prompt_text = row['prompt_text']
                except (KeyError, IndexError):
                    try:
                        prompt_text = row[0]
                    except (KeyError, IndexError):
                        prompt_text = None
            # Если это dict
            elif isinstance(row, dict):
                prompt_text = row.get('prompt_text', '')
            # Если это tuple или list
            elif isinstance(row, (tuple, list)) and len(row) > 0:
                prompt_text = row[0]
            else:
                prompt_text = None

            # Убеждаемся, что это строка
            if prompt_text is not None:
                print(f"🔍 DEBUG get_prompt_from_db: prompt_text type before conversion = {type(prompt_text)}", flush=True)
                prompt_text = str(prompt_text) if not isinstance(prompt_text, str) else prompt_text
                print(f"🔍 DEBUG get_prompt_from_db: prompt_text type after conversion = {type(prompt_text)}", flush=True)
                if prompt_text.strip():
                    return prompt_text

            # Если не удалось извлечь - используем fallback
            if fallback:
                print(f"⚠️ Не удалось извлечь промпт из row, используем fallback. Row type: {type(row)}, Row value: {row}", flush=True)
                return fallback
            else:
                return ""
        elif fallback:
            return fallback
        else:
            return ""
    except Exception as e:
        print(f"⚠️ Ошибка получения промпта из БД: {e}")
        import traceback
        traceback.print_exc()
        return fallback or ""

@app.route('/api/superadmin/users', methods=['GET'])
def get_all_users():
    """Получить всех пользователей (только для суперадмина)"""
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

        users = db.get_all_users()
        db.close()

        return jsonify({"success": True, "users": users})

    except Exception as e:
        print(f"❌ Ошибка получения пользователей: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/users-with-businesses', methods=['GET'])
def get_users_with_businesses():
    """Получить всех пользователей с их бизнесами и сетями (для админской страницы)"""
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
            return jsonify({"error": "Недостаточно прав"}), 403

        users_with_businesses = db.get_all_users_with_businesses()

        total_blocked = 0
        for user in users_with_businesses:
            blocked_direct = sum(1 for b in user.get('direct_businesses', []) if b.get('is_active') == 0)
            blocked_network = sum(1 for network in user.get('networks', []) for b in network.get('businesses', []) if b.get('is_active') == 0)
            total_blocked += blocked_direct + blocked_network
        logger.debug("Admin users-with-businesses blocked business count: %s", total_blocked)

        db.close()

        return jsonify({"success": True, "users": users_with_businesses})

    except Exception as e:
        logger.exception("Admin users-with-businesses failed")
        payload = {
            "detail": "internal_error in /api/admin/users-with-businesses",
            "where": "main.get_users_with_businesses",
            "error_type": e.__class__.__name__,
            "error": str(e),
        }
        if app.debug:
            import traceback
            payload["traceback"] = traceback.format_exc()
        return jsonify(payload), 500

@app.route('/api/admin/subscriptions/overview', methods=['GET'])
def get_admin_subscriptions_overview():
    """Операционный обзор подписок, автоплатежей и кредитов для суперадмина."""
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
            db.close()
            return jsonify({"error": "Недостаточно прав"}), 403

        cursor = db.conn.cursor()
        cursor.execute(
            """
            SELECT
                s.id,
                s.user_id,
                s.business_id,
                s.tariff_id,
                s.pending_tariff_id,
                s.status,
                s.period_start,
                s.next_billing_date,
                s.payment_method_id IS NOT NULL AS payment_method_linked,
                s.last_payment_id,
                s.retry_count,
                s.next_retry_at,
                s.created_at,
                s.updated_at,
                u.email AS user_email,
                u.name AS user_name,
                u.is_active AS user_is_active,
                COALESCE(u.credits_balance, 0) AS credits_balance,
                b.name AS business_name,
                b.subscription_tier AS business_subscription_tier,
                b.subscription_status AS business_subscription_status,
                b.subscription_ends_at AS business_subscription_ends_at,
                latest_attempt.status AS latest_attempt_status,
                latest_attempt.attempt_type AS latest_attempt_type,
                latest_attempt.payment_id AS latest_attempt_payment_id,
                latest_attempt.error_message AS latest_attempt_error,
                latest_attempt.created_at AS latest_attempt_at
            FROM subscriptions s
            JOIN users u ON u.id = s.user_id
            LEFT JOIN businesses b ON b.id = s.business_id
            LEFT JOIN LATERAL (
                SELECT status, attempt_type, payment_id, error_message, created_at
                FROM billing_attempts
                WHERE subscription_id = s.id
                ORDER BY created_at DESC
                LIMIT 1
            ) latest_attempt ON TRUE
            ORDER BY
                CASE WHEN s.status = 'blocked' THEN 0 WHEN s.status = 'active' THEN 1 ELSE 2 END,
                COALESCE(s.next_retry_at, s.next_billing_date, s.updated_at) ASC
            LIMIT 300
            """
        )
        subscriptions = [_row_to_dict(cursor, row) for row in (cursor.fetchall() or [])]

        cursor.execute(
            """
            SELECT
                ba.id,
                ba.subscription_id,
                ba.attempt_type,
                ba.attempt_no,
                ba.status,
                ba.payment_id,
                ba.amount_value,
                ba.currency,
                ba.error_message,
                ba.created_at,
                ba.updated_at,
                u.email AS user_email,
                b.name AS business_name
            FROM billing_attempts ba
            JOIN subscriptions s ON s.id = ba.subscription_id
            JOIN users u ON u.id = s.user_id
            LEFT JOIN businesses b ON b.id = s.business_id
            ORDER BY ba.created_at DESC
            LIMIT 30
            """
        )
        attempts = [_row_to_dict(cursor, row) for row in (cursor.fetchall() or [])]

        cursor.execute(
            """
            SELECT
                cl.id,
                cl.user_id,
                cl.subscription_id,
                cl.delta,
                cl.reason,
                cl.period_start,
                cl.period_end,
                cl.external_id,
                cl.created_at,
                u.email AS user_email,
                b.name AS business_name
            FROM credit_ledger cl
            JOIN users u ON u.id = cl.user_id
            LEFT JOIN subscriptions s ON s.id = cl.subscription_id
            LEFT JOIN businesses b ON b.id = s.business_id
            ORDER BY cl.created_at DESC
            LIMIT 30
            """
        )
        ledger = [_row_to_dict(cursor, row) for row in (cursor.fetchall() or [])]

        cursor.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days') AS new_users_30d,
                COUNT(*) FILTER (WHERE COALESCE(is_active, TRUE) = FALSE) AS inactive_users_total,
                COUNT(*) AS users_total
            FROM users
            """
        )
        user_metrics = _row_to_dict(cursor, cursor.fetchone()) or {}

        db.close()

        now = datetime.now(timezone.utc)
        tariff_amounts = {
            tariff_id: float(config.get("amount", 0))
            for tariff_id, config in TARIFFS.items()
        }

        def parse_admin_dt(value):
            if not value:
                return None
            if isinstance(value, datetime):
                return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            try:
                text = str(value)
                if text.endswith("Z"):
                    text = text[:-1] + "+00:00"
                parsed = datetime.fromisoformat(text)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except Exception:
                return None

        def serialize_admin_value(value):
            if isinstance(value, datetime):
                dt = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
                return dt.isoformat()
            return value

        def serialize_admin_row(row):
            return {key: serialize_admin_value(value) for key, value in (row or {}).items()}

        active_subscriptions = [item for item in subscriptions if str(item.get("status") or "") == "active"]
        blocked_subscriptions = [item for item in subscriptions if str(item.get("status") or "") == "blocked"]
        canceled_subscriptions = [item for item in subscriptions if str(item.get("status") or "") == "canceled"]
        autopay_enabled = [item for item in active_subscriptions if bool(item.get("payment_method_linked"))]
        missing_payment_method = [item for item in active_subscriptions if not bool(item.get("payment_method_linked"))]
        due_soon_count = 0
        overdue_count = 0
        blocked_30d = 0

        for item in subscriptions:
            status = str(item.get("status") or "")
            next_billing = parse_admin_dt(item.get("next_billing_date"))
            updated_at = parse_admin_dt(item.get("updated_at"))
            if status == "active" and next_billing:
                if next_billing <= now:
                    overdue_count += 1
                elif next_billing <= now + timedelta(days=7):
                    due_soon_count += 1
            if status in {"blocked", "canceled"} and updated_at and updated_at >= now - timedelta(days=30):
                blocked_30d += 1

        monthly_recurring_revenue = 0.0
        for item in active_subscriptions:
            monthly_recurring_revenue += tariff_amounts.get(str(item.get("tariff_id") or ""), 0.0)

        summary = {
            "subscriptions_total": len(subscriptions),
            "active_subscriptions": len(active_subscriptions),
            "blocked_subscriptions": len(blocked_subscriptions),
            "canceled_subscriptions": len(canceled_subscriptions),
            "autopay_enabled": len(autopay_enabled),
            "missing_payment_method": len(missing_payment_method),
            "due_soon_7d": due_soon_count,
            "overdue": overdue_count,
            "new_users_30d": int(user_metrics.get("new_users_30d") or 0),
            "inactive_users_total": int(user_metrics.get("inactive_users_total") or 0),
            "churned_or_blocked_30d": blocked_30d,
            "users_total": int(user_metrics.get("users_total") or 0),
            "monthly_recurring_revenue": monthly_recurring_revenue,
            "currency": "RUB",
        }

        return jsonify({
            "success": True,
            "summary": summary,
            "subscriptions": [serialize_admin_row(item) for item in subscriptions],
            "recent_attempts": [serialize_admin_row(item) for item in attempts],
            "credit_ledger": [serialize_admin_row(item) for item in ledger],
        })

    except Exception as e:
        logger.exception("Admin subscriptions overview failed")
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/businesses/<business_id>/block', methods=['POST'])
def block_business(business_id):
    """Заблокировать/разблокировать бизнес (только для demyanovap@yandex.ru)"""
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
            return jsonify({"error": "Доступ запрещён"}), 403
        db.close()

        data = request.get_json()
        is_blocked = data.get('is_blocked', True)

        db = DatabaseManager()
        success = db.block_business(business_id, is_blocked)
        db.close()

        if success:
            return jsonify({"success": True, "message": "Бизнес заблокирован" if is_blocked else "Бизнес разблокирован"})
        else:
            return jsonify({"error": "Бизнес не найден"}), 404

    except Exception as e:
        print(f"❌ Ошибка блокировки бизнеса: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/businesses/<business_id>/promo', methods=['POST'])
def set_promo_tier(business_id):
    """Установить/отключить оплаченный тариф для бизнеса (только для суперадмина)."""
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
            return jsonify({"error": "Доступ запрещён"}), 403

        data = request.get_json(silent=True) or {}
        is_promo = data.get('is_promo', True)
        requested_tier = str(data.get('tier') or 'promo').strip().lower()
        allowed_tiers = {'starter', 'professional', 'concierge', 'elite', 'promo', 'basic', 'pro', 'enterprise'}
        next_tier = requested_tier if requested_tier in allowed_tiers else 'promo'
        subscription_ends_at = data.get('subscription_ends_at') if is_promo else None

        cursor = db.conn.cursor()

        # Проверяем, что бизнес существует
        cursor.execute("SELECT id FROM businesses WHERE id = %s", (business_id,))
        business = cursor.fetchone()

        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        # Защитный DDL для PostgreSQL: добавляем колонки, если их нет
        cursor.execute(
            "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'trial'"
        )
        cursor.execute(
            "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'active'"
        )
        cursor.execute(
            "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS subscription_ends_at TIMESTAMP"
        )
        cursor.execute(
            "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )

        # Устанавливаем или отключаем оплаченный тариф
        if is_promo:
            cursor.execute("""
                UPDATE businesses
                SET subscription_tier = %s,
                    subscription_status = 'active',
                    subscription_ends_at = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (next_tier, subscription_ends_at, business_id))
            message = "Оплаченный тариф установлен"
        else:
            cursor.execute("""
                UPDATE businesses
                SET subscription_tier = 'trial',
                    subscription_status = 'inactive',
                    subscription_ends_at = NULL,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (business_id,))
            message = "Оплаченный тариф отключен"

        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "message": message,
            "subscription_tier": next_tier if is_promo else 'trial',
            "subscription_status": 'active' if is_promo else 'inactive',
            "subscription_ends_at": subscription_ends_at,
        })

    except Exception as e:
        print(f"❌ Ошибка установки промо тарифа: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/networks/<network_id>/promo', methods=['POST'])
def set_network_promo_tier(network_id):
    """Установить/отключить оплаченный тариф для всех бизнесов сети."""
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
            db.close()
            return jsonify({"error": "Доступ запрещён"}), 403

        data = request.get_json(silent=True) or {}
        is_promo = data.get('is_promo', True)
        requested_tier = str(data.get('tier') or 'promo').strip().lower()
        allowed_tiers = {'starter', 'professional', 'concierge', 'elite', 'promo', 'basic', 'pro', 'enterprise'}
        next_tier = requested_tier if requested_tier in allowed_tiers else 'promo'
        subscription_ends_at = data.get('subscription_ends_at') if is_promo else None
        cursor = db.conn.cursor()

        cursor.execute("SELECT id, name FROM networks WHERE id = %s", (network_id,))
        network = cursor.fetchone()
        if not network:
            db.close()
            return jsonify({"error": "Сеть не найдена"}), 404

        cursor.execute(
            "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'trial'"
        )
        cursor.execute(
            "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'active'"
        )
        cursor.execute(
            "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS subscription_ends_at TIMESTAMP"
        )
        cursor.execute(
            "ALTER TABLE businesses ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        )

        next_tier = next_tier if is_promo else 'trial'
        next_status = 'active' if is_promo else 'inactive'
        cursor.execute("""
            UPDATE businesses
            SET subscription_tier = %s,
                subscription_status = %s,
                subscription_ends_at = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE network_id = %s OR id = %s
        """, (next_tier, next_status, subscription_ends_at, network_id, network_id))
        updated_count = cursor.rowcount

        db.conn.commit()
        db.close()

        message = "Оплаченный тариф установлен для сети" if is_promo else "Оплаченный тариф отключен для сети"
        return jsonify({
            "success": True,
            "message": message,
            "updated_count": updated_count,
            "subscription_tier": next_tier,
            "subscription_status": next_status,
            "subscription_ends_at": subscription_ends_at,
        })

    except Exception as e:
        print(f"❌ Ошибка установки промо тарифа для сети: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/business/<business_id>/network-locations', methods=['GET'])
def get_network_locations(business_id):
    """Получить все точки сети для бизнеса (если пользователь является владельцем сети)"""
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

        # Получаем бизнес
        business = db.get_business_by_id(business_id)
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        # ! FIX: Получаем только точки ТОЙ ЖЕ сети, к которой принадлежит бизнес
        network_id = business.get('network_id')
        print(f"🔍 API DEBUG: Business {business_id} ({business.get('name')}) -> Network {network_id}")

        network_id_value = str(network_id or "").strip()
        business_id_value = str(business_id or "").strip()
        is_network_master = bool(network_id_value) and business_id_value == network_id_value
        is_network_member = bool(network_id_value) and business_id_value != network_id_value

        if not network_id:
            print("🔍 API DEBUG: No network_id, returning []")
            db.close()
            return jsonify({
                "success": True,
                "is_network": False,
                "is_network_master": False,
                "is_network_member": False,
                "network_id": None,
                "locations": [],
            })

        locations = db.get_businesses_by_network(network_id)
        print(f"🔍 API DEBUG: Found {len(locations)} locations for network {network_id}")

        # Нормализация: алиас website = site для фронта, пустые строки вместо NULL
        def _norm_loc(loc):
            if not loc or not isinstance(loc, dict):
                return loc
            site_val = loc.get("site") or loc.get("website") or ""
            out = {k: (v if v is not None else "") for k, v in loc.items() if isinstance(k, str)}
            out["website"] = site_val
            out["site"] = loc.get("site") or loc.get("website") or ""
            return out

        cursor = db.conn.cursor()
        normalized_locations = [_norm_loc(loc) for loc in locations]
        representative_id = None
        if normalized_locations:
            def _normalized_name(value):
                return " ".join(
                    re.sub(r"[^\w\s]+", " ", str(value or "").lower().replace("ё", "е")).split()
                )

            name_counts = {}
            for loc in normalized_locations:
                name_key = _normalized_name(loc.get("name"))
                if not name_key:
                    continue
                name_counts[name_key] = int(name_counts.get(name_key) or 0) + 1

            explicit_parent = next((loc for loc in normalized_locations if str(loc.get("id") or "") == str(network_id)), None)
            representative = explicit_parent
            if representative is None:
                unique_candidates = []
                for loc in normalized_locations:
                    normalized_name = _normalized_name(loc.get("name"))
                    if normalized_name and int(name_counts.get(normalized_name) or 0) == 1:
                        unique_candidates.append(loc)
                if unique_candidates:
                    unique_candidates.sort(
                        key=lambda loc: (
                            -len(_normalized_name(loc.get("name")).split()),
                            -len(str(loc.get("name") or "")),
                            str(loc.get("created_at") or ""),
                        )
                    )
                    representative = unique_candidates[0]
                else:
                    representative = sorted(
                        normalized_locations,
                        key=lambda loc: (
                            str(loc.get("created_at") or ""),
                            str(loc.get("name") or ""),
                        ),
                    )[0]
            representative_id = str(representative.get("id") or "") if representative else None
            for loc in normalized_locations:
                loc["is_network_parent"] = bool(representative_id) and str(loc.get("id") or "") == representative_id
                resolved_lat, resolved_lon = _resolve_business_coordinates(
                    cursor,
                    str(loc.get("id") or ""),
                    str(loc.get("address") or ""),
                    loc.get("geo_lat"),
                    loc.get("geo_lon"),
                )
                loc["geo_lat"] = resolved_lat
                loc["geo_lon"] = resolved_lon
        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "is_network": is_network_master,
            "is_network_master": is_network_master,
            "is_network_member": is_network_member,
            "network_id": network_id,
            "locations": normalized_locations,
            "parent_business_id": representative_id,
        })

    except Exception as e:
        print(f"❌ Ошибка получения точек сети: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

def _upsert_network_parent_business(cursor, network_id: str, owner_id: str, network_name: str, description: str = "") -> None:
    business_name = str(network_name or "").strip() or "Сеть"
    business_description = (
        str(description or "").strip()
        or f"Материнская точка сети {business_name}. Здесь собираются отзывы, новости и данные по всей сети."
    )

    cursor.execute("SELECT id FROM businesses WHERE id = %s", (network_id,))
    existing = cursor.fetchone()
    if existing:
        cursor.execute(
            """
            UPDATE businesses
            SET owner_id = %s,
                name = %s,
                network_id = %s,
                description = %s,
                address = %s,
                is_active = TRUE,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (
                owner_id,
                business_name,
                network_id,
                business_description,
                "Материнская точка сети",
                network_id,
            ),
        )
        return

    cursor.execute(
        """
        INSERT INTO businesses (
            id, owner_id, name, network_id, description, address, is_active, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, TRUE, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """,
        (
            network_id,
            owner_id,
            business_name,
            network_id,
            business_description,
            "Материнская точка сети",
        ),
    )

@app.route('/api/business/<business_id>/data', methods=['GET'])
def get_business_data(business_id):
    """Получить полные данные конкретного бизнеса"""
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

        # Создаем таблицу FinancialTransactions если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS FinancialTransactions (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                business_id TEXT,
                transaction_type TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                category TEXT,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)

        # Создаем таблицу BusinessProfiles если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessProfiles (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                contact_name TEXT,
                contact_phone TEXT,
                contact_email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)

        # Добавляем поле business_id в UserServices если его нет
        try:
            cursor.execute("ALTER TABLE UserServices ADD COLUMN business_id TEXT")
            cursor.execute("""
                UPDATE UserServices
                SET business_id = (
                    SELECT b.id FROM Businesses b
                    WHERE b.owner_id = UserServices.user_id
                    LIMIT 1
                )
                WHERE business_id IS NULL
            """)
        except Exception:
            # Поле уже существует или другая ошибка
            pass

        db.conn.commit()

        # Проверяем доступ к бизнесу
        business = db.get_business_by_id(business_id)
        if not business:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        # Проверяем права доступа
        if not db.is_superadmin(user_data['user_id']) and business['owner_id'] != user_data['user_id']:
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Получаем услуги бизнеса
        services = db.get_services_by_business(business_id)

        # Получаем финансовые данные бизнеса
        financial_data = db.get_financial_data_by_business(business_id)

        # Получаем отчеты бизнеса
        reports = db.get_reports_by_business(business_id)

        # Получаем профиль бизнеса
        cursor.execute("""
            SELECT contact_name, contact_phone, contact_email
            FROM BusinessProfiles
            WHERE business_id = %s
        """, (business_id,))
        profile_row = cursor.fetchone()
        business_profile = {
            "contact_name": profile_row[0] if profile_row else "",
            "contact_phone": profile_row[1] if profile_row else "",
            "contact_email": profile_row[2] if profile_row else ""
        } if profile_row else {
            "contact_name": "",
            "contact_phone": "",
            "contact_email": ""
        }

        db.close()

        return jsonify({
            "success": True,
            "business": business,
            "business_profile": business_profile,
            "services": services,
            "financial_data": financial_data,
            "reports": reports
        })

    except Exception as e:
        print(f"❌ Ошибка получения данных бизнеса: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/business/<business_id>/yandex-link', methods=['POST', 'OPTIONS'])
def update_business_yandex_link(business_id):
    """Обновление ссылки/ID Яндекс.Карт для бизнеса и запуск синхронизации (по возможности)."""
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

        data = request.get_json(silent=True) or {}
        yandex_url = (data.get('yandex_url') or '').strip()

        if not yandex_url:
            return jsonify({"error": "Не указана ссылка на Яндекс.Карты"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем права доступа к бизнесу
        owner_id = get_business_owner_id(cursor, business_id)
        if not owner_id:
            db.close()
            return jsonify({"error": "Бизнес не найден"}), 404

        if owner_id != user_data['user_id'] and not user_data.get('is_superadmin'):
            db.close()
            return jsonify({"error": "Нет доступа к этому бизнесу"}), 403

        # Обновляем ссылку и, при возможности, yandex_org_id
        from yandex_adapter import YandexAdapter

        adapter = YandexAdapter()
        org_id = adapter.parse_org_id_from_url(yandex_url)

        cursor.execute(
            """
            UPDATE Businesses
            SET yandex_url = %s, yandex_org_id = %s
            WHERE id = %s
            """,
            (yandex_url, org_id, business_id),
        )

        db.conn.commit()
        db.close()

        # Пытаемся запустить синхронизацию (если есть org_id и настроен адаптер)
        synced = False
        try:
            if org_id and YandexSyncService is not None:
                sync_service = YandexSyncService()
                synced = sync_service.sync_business(business_id)
        except Exception as sync_err:
            print(f"⚠️ Ошибка при синхронизации Яндекс после обновления ссылки: {sync_err}")

        return jsonify(
            {
                "success": True,
                "synced": bool(synced),
                "message": "Ссылка Яндекс.Карт обновлена",
            }
        )
    except Exception as e:
        return jsonify({"error": f"Ошибка обновления ссылки Яндекс.Карт: {str(e)}"}), 500

@app.route('/api/business/<business_id>/profile', methods=['POST', 'OPTIONS'])
def update_business_profile(business_id):
    """Обновить профиль бизнеса"""
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Создаем таблицу BusinessProfiles если её нет
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessProfiles (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                contact_name TEXT,
                contact_phone TEXT,
                contact_email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE CASCADE
            )
        """)

        # Обновляем или создаем профиль бизнеса
        profile_id = f"profile_{business_id}"
        cursor.execute("""
            INSERT INTO BusinessProfiles (
                id,
                business_id,
                contact_name,
                contact_phone,
                contact_email,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE
            SET business_id = EXCLUDED.business_id,
                contact_name = EXCLUDED.contact_name,
                contact_phone = EXCLUDED.contact_phone,
                contact_email = EXCLUDED.contact_email,
                updated_at = CURRENT_TIMESTAMP
        """, (
            profile_id,
            business_id,
            data.get('contact_name', ''),
            data.get('contact_phone', ''),
            data.get('contact_email', '')
        ))

        db.conn.commit()
        db.close()

        return jsonify({"success": True, "message": "Профиль бизнеса обновлен"})

    except Exception as e:
        print(f"❌ Ошибка обновления профиля бизнеса: {e}")
        return jsonify({"error": str(e)}), 500

def send_email(to_email, subject, body, from_name="LocalOS"):
    """Универсальная функция для отправки email"""
    return deliver_email(to_email, subject, body, from_name)

def send_contact_email(name, email, phone, message):
    """Отправка email с сообщением обратной связи"""
    contact_email = os.getenv("CONTACT_EMAIL", "info@localos.pro")

    subject = f"Новое сообщение с сайта LocalOS от {name}"
    body = f"""
Новое сообщение с сайта LocalOS

Имя: {name}
Email: {email}
Телефон: {phone if phone else 'Не указан'}

Сообщение:
{message}

---
Отправлено с сайта localos.pro
    """

    return send_email(contact_email, subject, body)

@app.route('/api/auth/reset-password', methods=['POST'])
@rate_limit_if_available("5 per hour")
def reset_password():
    """Запрос на восстановление пароля"""
    try:
        data = request.get_json()
        email = normalize_email(data.get('email'))

        if not email:
            return jsonify({"error": "Email обязателен"}), 400

        # Проверяем, существует ли пользователь
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, name FROM Users WHERE LOWER(email) = %s", (email,))
        user = cursor.fetchone()

        if not user:
            conn.close()
            return jsonify({
                "success": True,
                "message": "Если email зарегистрирован, инструкции по восстановлению будут отправлены"
            })

        # Генерируем токен восстановления
        import secrets
        from datetime import datetime, timedelta

        reset_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(hours=1)

        # Сохраняем токен в базе
        cursor.execute("""
            UPDATE Users
            SET reset_token = %s, reset_token_expires = %s
            WHERE LOWER(email) = %s
        """, (reset_token, expires_at.isoformat(), email))
        conn.commit()
        conn.close()

        # Отправляем реальное письмо
        subject = "Восстановление пароля LocalOS"
        body = f"""
Восстановление пароля для LocalOS

Ваш токен восстановления: {reset_token}
Действителен до: {expires_at.strftime('%d.%m.%Y %H:%M')}

Для сброса пароля перейдите по ссылке:
https://localos.pro/reset-password?token={reset_token}&email={email}

Если вы не запрашивали восстановление пароля, проигнорируйте это письмо.

---
LocalOS
        """

        email_sent = send_email(email, subject, body)

        if email_sent:
            print(f"✅ Email отправлен на {email}")
        else:
            print(f"❌ Не удалось отправить email на {email}")

        return jsonify({
            "success": True,
            "message": "Инструкции по восстановлению пароля отправлены на email"
        })

    except Exception as e:
        print(f"❌ Ошибка восстановления пароля: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/set-password', methods=['POST'])
@rate_limit_if_available("10 per hour")
def auth_set_password():
    """Установка пароля для недавно созданного passwordless-аккаунта."""
    try:
        data = request.get_json(silent=True) or {}
        email = str(data.get('email') or '').strip().lower()
        password = str(data.get('password') or '')
        setup_token = str(data.get('token') or '').strip()
        personal_data_consent = bool(data.get('personal_data_consent'))
        consent_version = str(data.get('consent_version') or CONSENT_VERSION).strip()

        if not email or not password:
            return jsonify({"error": "Email и пароль обязательны"}), 400
        if len(password) < 6:
            return jsonify({"error": "Пароль должен содержать минимум 6 символов"}), 400
        if not setup_token:
            return jsonify({"error": "Ссылка установки пароля недействительна или устарела"}), 400
        if not personal_data_consent:
            return jsonify({"error": "Необходимо согласие на обработку персональных данных"}), 400

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'users'
                """
            )
            user_columns = {
                str((row.get('column_name') if hasattr(row, 'get') else row[0]) or '').lower()
                for row in (cursor.fetchall() or [])
            }
            cursor.execute(
                """
                SELECT id, email, name, phone, password_hash, verification_token
                FROM users
                WHERE LOWER(email) = %s
                LIMIT 1
                """,
                (email,),
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({"error": "Пользователь с таким email не найден"}), 404

            user_id = row.get('id') if hasattr(row, 'get') else row[0]
            user_email = row.get('email') if hasattr(row, 'get') else row[1]
            user_name = row.get('name') if hasattr(row, 'get') else row[2]
            user_phone = row.get('phone') if hasattr(row, 'get') else row[3]
            password_hash = row.get('password_hash') if hasattr(row, 'get') else row[4]
            verification_token = row.get('verification_token') if hasattr(row, 'get') else row[5]
        finally:
            conn.close()

        if str(password_hash or '').strip():
            return jsonify({"error": "Для этого аккаунта пароль уже установлен. Используйте восстановление пароля."}), 400
        if not str(verification_token or '').strip() or setup_token != str(verification_token):
            return jsonify({"error": "Ссылка установки пароля недействительна или устарела"}), 400

        from auth_system import set_password

        result = set_password(str(user_id), password)
        if result.get('error'):
            return jsonify(result), 400

        conn = get_db_connection()
        try:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            updates = ["verification_token = NULL", "is_verified = %s", "updated_at = %s"]
            values = [True, now]
            optional_updates = {
                "email_verified_at": now,
                "personal_data_consent_at": now,
                "personal_data_consent_version": consent_version,
                "privacy_accepted_at": now,
                "terms_accepted_at": now,
                "consent_ip": request.headers.get('X-Forwarded-For') or request.remote_addr,
                "consent_user_agent": request.headers.get('User-Agent'),
            }
            for column, value in optional_updates.items():
                if column in user_columns:
                    updates.append(f"{column} = %s")
                    values.append(value)
            values.append(str(user_id))
            cursor.execute(
                f"UPDATE users SET {', '.join(updates)} WHERE id = %s",
                tuple(values),
            )
            conn.commit()
        finally:
            conn.close()

        session_token = create_session(
            str(user_id),
            ip_address=request.headers.get('X-Forwarded-For') or request.remote_addr,
            user_agent=request.headers.get('User-Agent'),
        )
        return jsonify(
            {
                "success": True,
                "id": str(user_id),
                "email": str(user_email or ''),
                "name": str(user_name or ''),
                "phone": str(user_phone or ''),
                "token": session_token,
            }
        )
    except Exception as e:
        print(f"❌ Ошибка установки пароля: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/auth/confirm-reset', methods=['POST'])
@rate_limit_if_available("5 per hour")
def confirm_reset():
    """Подтверждение сброса пароля с новым паролем"""
    try:
        data = request.get_json()
        email = normalize_email(data.get('email'))
        token = data.get('token')
        new_password = data.get('password')

        if not all([email, token, new_password]):
            return jsonify({"error": "Все поля обязательны"}), 400

        # Проверяем токен
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, reset_token, reset_token_expires
            FROM Users
            WHERE LOWER(email) = %s AND reset_token = %s
        """, (email, token))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Неверный токен"}), 400

        # Проверяем срок действия токена
        from datetime import datetime
        if datetime.now() > datetime.fromisoformat(user[2]):
            return jsonify({"error": "Токен истек"}), 400

        # Устанавливаем новый пароль
        from auth_system import set_password
        result = set_password(user[0], new_password)

        if 'error' in result:
            return jsonify(result), 400

        # Очищаем токен
        cursor.execute("""
            UPDATE Users
            SET reset_token = NULL, reset_token_expires = NULL
            WHERE id = %s
        """, (user[0],))
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "Пароль успешно изменен"})

    except Exception as e:
        print(f"❌ Ошибка подтверждения сброса: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/public/request-report', methods=['POST', 'OPTIONS'])
@rate_limit_if_available("10 per hour")
def public_request_report():
    """Публичная заявка на отчёт без авторизации.
    Создаёт публичную страницу аудита, запускает фоновый парсинг карты и возвращает ссылку на отчёт.
    """
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400

        email = data.get('email', '').strip()
        url = data.get('url', '').strip()

        if not email or not url:
            return jsonify({"error": "Email и URL обязательны"}), 400

        source = _detect_public_map_source(url)
        name_hint = str(data.get("name") or "").strip()
        city_hint = str(data.get("city") or "").strip()
        address_hint = str(data.get("address") or "").strip()
        slug_seed = _build_public_report_display_name(name_hint, city_hint, address_hint)
        if not slug_seed or slug_seed == "Компания":
            slug_seed = re.sub(r"https?://", "", url).split("/", 1)[-1].replace("/", "-")
        normalized_slug = _slugify_public_report_name(slug_seed)
        telegram_chat_id = str(data.get("telegram_chat_id") or "").strip()
        telegram_notify_when_ready = bool(data.get("telegram_notify_when_ready"))
        pending_page = _build_public_pending_page(email=email, map_url=url)
        if telegram_chat_id and telegram_notify_when_ready:
            pending_page["telegram_notification"] = {
                "chat_id": telegram_chat_id,
                "notify_when_ready": True,
                "source": str(data.get("source") or "").strip() or "public_request",
                "created_at": datetime.utcnow().isoformat(),
            }

        conn = get_db_connection()
        try:
            _ensure_public_report_requests_table(conn)
            cur = conn.cursor()
            suffix = 0
            slug = normalized_slug
            while True:
                cur.execute("SELECT slug FROM publicreportrequests WHERE slug = %s LIMIT 1", (slug,))
                existing = cur.fetchone()
                if not existing:
                    break
                suffix += 1
                slug = f"{normalized_slug}-{suffix}"

            cur.execute(
                """
                INSERT INTO publicreportrequests (slug, email, source_url, source, status, page_json, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, NOW(), NOW())
                """,
                (slug, email, url, source, "queued", json.dumps(pending_page, ensure_ascii=False)),
            )
            conn.commit()
        finally:
            conn.close()

        # Асинхронный запуск: сразу возвращаем ссылку на страницу, а данные подтянутся после парсинга.
        thread = threading.Thread(target=_run_public_report_pipeline, args=(slug,), daemon=True)
        thread.start()

        frontend_base = str(os.getenv("FRONTEND_BASE_URL") or os.getenv("PUBLIC_DOMAIN") or "https://localos.pro").strip().rstrip("/")
        public_url = f"{frontend_base}/{slug}" if frontend_base else f"/{slug}"

        _notify_public_report_request_async(email, url, public_url)

        # Логирование в консоль
        print(f"📧 НОВАЯ ЗАЯВКА ОТ {email}:")
        print(f"🔗 URL: {url}")
        print(f"📄 Публичная страница: {public_url}")
        print("-" * 50)

        return jsonify({
            "success": True,
            "message": "Заявка принята. Формируем отчёт.",
            "slug": slug,
            "public_url": public_url,
        }), 200

    except Exception as e:
        print(f"❌ Ошибка обработки заявки: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/public/request-registration', methods=['POST', 'OPTIONS'])
@rate_limit_if_available("10 per hour")
def public_request_registration():
    """Публичная заявка на регистрацию без авторизации.
    Принимает данные регистрации, отправляет email на info@localos.pro о новой заявке.
    """
    try:
        if request.method == 'OPTIONS':
            return ('', 204)

        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400

        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        yandex_url = data.get('yandex_url', '').strip()

        if not email:
            return jsonify({"error": "Email обязателен"}), 400

        # Отправляем email на info@localos.pro о новой заявке на регистрацию
        contact_email = os.getenv("CONTACT_EMAIL", "info@localos.pro")
        subject = f"Новая заявка на регистрацию от {email}"
        body = f"""
Новая заявка на регистрацию с сайта LocalOS

Имя: {name or 'Не указано'}
Email: {email}
Телефон: {phone or 'Не указан'}
Ссылка на Яндекс.Карты: {yandex_url or 'Не указана'}

---
Отправлено с сайта localos.pro
        """

        email_sent = send_email(contact_email, subject, body)
        if not email_sent:
            print("⚠️ Не удалось отправить email")

        # Логирование в консоль
        print(f"📧 НОВАЯ ЗАЯВКА НА РЕГИСТРАЦИЮ ОТ {email}:")
        print(f"👤 Имя: {name or 'Не указано'}")
        print(f"📞 Телефон: {phone or 'Не указан'}")
        print(f"🔗 Яндекс.Карты: {yandex_url or 'Не указана'}")
        print("-" * 50)

        return jsonify({
            "success": True,
            "message": "Заявка на регистрацию принята. Мы свяжемся с вами в ближайшее время."
        }), 200

    except Exception as e:
        print(f"❌ Ошибка обработки заявки на регистрацию: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/telegram/bind', methods=['POST'])
def generate_telegram_bind_token():
    """Генерация токена для привязки Telegram аккаунта для конкретного бизнеса"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Получаем business_id из запроса
        data = request.get_json(silent=True) or {}
        business_id = data.get('business_id')

        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400

        # Проверяем, что бизнес принадлежит пользователю
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute("SELECT id FROM businesses WHERE id = %s AND owner_id = %s", (business_id, user_data['user_id']))
        business_row = cursor.fetchone()
        if not business_row:
            db.close()
            return jsonify({"error": "Бизнес не найден или не принадлежит вам"}), 403

        # Генерируем токен привязки
        import secrets
        from datetime import datetime, timedelta

        bind_token = secrets.token_urlsafe(32)
        expires_at = datetime.now() + timedelta(minutes=5)  # Токен действует 5 минут

        # Удаляем старые неиспользованные токены для этого бизнеса
        cursor.execute(
            """
            DELETE FROM telegrambindtokens
            WHERE business_id = %s
              AND used = 0
              AND expires_at < %s
            """,
            (business_id, datetime.now()),
        )

        # Создаем новый токен
        token_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO telegrambindtokens (id, user_id, business_id, token, expires_at, used, created_at)
            VALUES (%s, %s, %s, %s, %s, 0, %s)
            """,
            (token_id, user_data['user_id'], business_id, bind_token, expires_at, datetime.now()),
        )

        db.conn.commit()
        db.close()

        return jsonify({
            "success": True,
            "token": bind_token,
            "expires_at": expires_at.isoformat(),
            "qr_data": f"https://t.me/LocalOspro_bot?start={bind_token}"
        }), 200

    except Exception as e:
        print(f"❌ Ошибка генерации токена привязки: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/telegram/bind/status', methods=['GET'])
def get_telegram_bind_status():
    """Проверка статуса привязки Telegram аккаунта для конкретного бизнеса"""
    try:
        # Проверяем авторизацию
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        # Получаем business_id из query параметров
        business_id = request.args.get('business_id')

        if not business_id:
            return jsonify({"error": "business_id обязателен"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()

        # Проверяем, что бизнес принадлежит пользователю
        cursor.execute("SELECT id FROM businesses WHERE id = %s AND owner_id = %s", (business_id, user_data['user_id']))
        business_row = cursor.fetchone()
        if not business_row:
            db.close()
            return jsonify({"error": "Бизнес не найден или не принадлежит вам"}), 403

        # Проверяем, привязан ли Telegram для этого бизнеса
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM telegrambindtokens
            WHERE business_id = %s
              AND used = 1
              AND user_id = %s
            """,
            (business_id, user_data['user_id']),
        )
        result = cursor.fetchone()
        count_value = 0
        if result:
            if hasattr(result, "get"):
                count_value = int(result.get("count") or 0)
            else:
                count_value = int(result[0] or 0)
        has_used_token_for_this_business = count_value > 0

        cursor.execute("SELECT telegram_id FROM users WHERE id = %s", (user_data['user_id'],))
        user_row = cursor.fetchone()
        if user_row and hasattr(user_row, "get"):
            telegram_id = user_row.get("telegram_id")
        else:
            telegram_id = user_row[0] if user_row else None
        telegram_id = str(telegram_id or "").strip()
        is_linked = bool(has_used_token_for_this_business and telegram_id and telegram_id.lower() != "none")

        db.close()

        return jsonify({
            "success": True,
            "is_linked": is_linked,
            "telegram_id": telegram_id if is_linked else None
        }), 200

    except Exception as e:
        print(f"❌ Ошибка проверки статуса привязки: {e}")
        return jsonify({"error": str(e)}), 500
