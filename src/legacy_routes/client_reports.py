from legacy_routes import shared as _shared

globals().update(_shared.runtime_namespace)

@app.route('/api/news/generate', methods=['POST', 'OPTIONS'])
@rate_limit_if_available("30 per hour")
def news_generate():
    try:
        print(f"🔍 Начало обработки запроса /api/news/generate")
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
        use_service = bool(data.get('use_service'))
        use_transaction = bool(data.get('use_transaction'))
        content_mode = str(data.get('content_mode') or 'news').strip().lower()
        social_format = str(data.get('social_format') or '').strip().lower()
        ab_mode = str(data.get('ab_mode') or '').strip().lower()
        selected_service_id = data.get('service_id')
        selected_transaction_id = data.get('transaction_id')
        raw_info = (data.get('raw_info') or '').strip()

        def _build_news_generation_fallback(
            *,
            business_name: str,
            language_code: str,
            service_text: str,
            transaction_text: str,
            raw_text: str,
            mode: str,
            social_post_format: str,
            unavailable_reason: str,
        ) -> Dict[str, Any]:
            language_title_map = {
                "ru": "Новость компании",
                "en": "Business update",
                "el": "Ενημέρωση επιχείρησης",
            }
            language_cta_map = {
                "ru": "Запись и подробности — по телефону или в сообщениях.",
                "en": "For details or booking, contact us by phone or message.",
                "el": "Για λεπτομέρειες ή κράτηση, επικοινωνήστε τηλεφωνικά ή με μήνυμα.",
            }
            headline = language_title_map.get(language_code, "Business update")
            cta = language_cta_map.get(language_code, "For details or booking, contact us by phone or message.")

            context_parts = []
            if service_text:
                context_parts.append(service_text.replace("Услуга:", "").strip())
            if transaction_text:
                context_parts.append(transaction_text.replace("Выполнена работа:", "").strip())
            if raw_text:
                context_parts.append(raw_text.strip())

            core_context = ". ".join([part for part in context_parts if part])[:500].strip()
            if not core_context:
                if language_code == "ru":
                    core_context = "Мы обновили информацию о наших услугах и готовы подсказать подходящий формат визита."
                elif language_code == "el":
                    core_context = "Ενημερώσαμε τις υπηρεσίες μας και είμαστε έτοιμοι να σας βοηθήσουμε να επιλέξετε την κατάλληλη επίσκεψη."
                else:
                    core_context = "We updated our service information and are ready to help you choose the right visit format."

            if mode == "social":
                if language_code == "ru":
                    generated_text = f"{business_name}: {core_context} {cta}"
                elif language_code == "el":
                    generated_text = f"{business_name}: {core_context} {cta}"
                else:
                    generated_text = f"{business_name}: {core_context} {cta}"
            else:
                if language_code == "ru":
                    generated_text = f"{headline}: {core_context} {cta}"
                elif language_code == "el":
                    generated_text = f"{headline}: {core_context} {cta}"
                else:
                    generated_text = f"{headline}: {core_context} {cta}"

            recommendations = [unavailable_reason]
            if social_post_format:
                recommendations.append(f"Формат: {social_post_format}. Проверьте тон и адаптируйте текст под площадку перед публикацией.")
            else:
                recommendations.append("Проверьте формулировки и при необходимости отредактируйте текст вручную перед публикацией.")

            return {
                "news": generated_text[:1500],
                "fallback_used": True,
                "general_recommendations": recommendations,
            }

        def _analyze_news_text_with_fallback(
            prompt_text: str,
            *,
            business_name: str,
            language_code: str,
            service_text: str,
            transaction_text: str,
            raw_text: str,
            mode: str,
            social_post_format: str,
            business_id_value: str | None,
            user_id_value: str,
        ) -> str:
            try:
                return analyze_text_with_gigachat(
                    prompt_text,
                    task_type="news_generation",
                    business_id=business_id_value,
                    user_id=user_id_value
                )
            except Exception as exc:
                exc_text = str(exc or "")
                if "GigaChat ключи не настроены" not in exc_text:
                    raise
                fallback_result = _build_news_generation_fallback(
                    business_name=business_name,
                    language_code=language_code,
                    service_text=service_text,
                    transaction_text=transaction_text,
                    raw_text=raw_text,
                    mode=mode,
                    social_post_format=social_post_format,
                    unavailable_reason="GigaChat сейчас не настроен, поэтому применён базовый fallback без AI-генерации.",
                )
                print("⚠️ GigaChat не настроен, используем fallback для генерации новости", flush=True)
                return json.dumps(fallback_result, ensure_ascii=False)

        # Язык новости: получаем из запроса или из профиля пользователя
        requested_language = data.get('language')
        language = get_user_language(user_data['user_id'], requested_language)
        language_names = {
            'ru': 'Russian',
            'en': 'English',
            'es': 'Spanish',
            'de': 'German',
            'fr': 'French',
            'it': 'Italian',
            'pt': 'Portuguese',
            'zh': 'Chinese'
        }
        language_name = language_names.get(language, 'Russian')

        db = DatabaseManager()
        cur = db.conn.cursor()
        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id') or data.get('business_id'))
        business_name = "Бизнес"
        business_categories = ""
        business_type_context = ""
        industry_key = "local_business"
        active_news_patterns: list[dict] = []
        industry_pattern_context = format_industry_pattern_prompt("local_business", mode="news")
        if business_id:
            cur.execute(
                """
                SELECT name, business_type, industry, categories, address, description, site, website
                FROM businesses
                WHERE id = %s
                LIMIT 1
                """,
                (business_id,),
            )
            business_row = cur.fetchone()
            if business_row:
                business_data = _row_to_dict(cur, business_row)
                business_name = str(business_data.get('name') or "").strip() or business_name
                business_categories = str(business_data.get('categories') or "").strip()
                business_context_parts = [
                    str(business_data.get('business_type') or "").strip(),
                    str(business_data.get('industry') or "").strip(),
                    business_categories,
                    str(business_data.get('address') or "").strip(),
                ]
                if not use_service:
                    business_context_parts.extend(
                        [
                            str(business_data.get('description') or "").strip(),
                            str(business_data.get('site') or business_data.get('website') or "").strip(),
                        ]
                    )
                business_type_context = " | ".join(item for item in business_context_parts if item)
                if not use_service:
                    site_description = _fetch_news_site_description(
                        business_data.get('site') or business_data.get('website')
                    )
                    if site_description:
                        business_type_context = " | ".join(
                            item for item in [business_type_context, f"Описание сайта: {site_description}"] if item
                        )
                industry_key = detect_industry_key(
                    business_name=business_name,
                    business_type=business_data.get('business_type'),
                    industry=business_data.get('industry'),
                    categories=business_data.get('categories'),
                )
                industry_pattern_context = format_industry_pattern_prompt(industry_key, mode="news")
                active_news_patterns = load_active_industry_patterns(db.conn, industry_key, "news")
                active_news_pattern_text = format_loaded_active_industry_patterns(active_news_patterns)
                if active_news_pattern_text:
                    industry_pattern_context += f"\n{active_news_pattern_text}"
        business_context = f"Название бизнеса: {business_name}. Тип/категории/адрес: {business_type_context or 'не указано'}."
        forbidden_industry_examples = (
            "Не выдумывай услуги, товары, режим работы, акции или отрасль. "
            "Если в примерах есть другая отрасль, игнорируй такие примеры. "
            "Для АЗС запрещены темы пекарни, булочек, круассанов, тортов, салона красоты, медицинских услуг и любых услуг, которых нет в контексте."
        )
        # ensure table
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS UserNews (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                service_id TEXT,
                source_text TEXT,
                generated_text TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                FOREIGN KEY (service_id) REFERENCES UserServices(id) ON DELETE SET NULL
            )
            """
        )
        _ensure_usernews_learning_columns(cur)

        service_context = ''
        transaction_context = ''

        if use_service:
            if selected_service_id:
                cur.execute(
                    "SELECT name, description FROM userservices WHERE id = %s AND user_id = %s",
                    (selected_service_id, user_data['user_id']),
                )
                row = cur.fetchone()
                if row:
                    name, desc = (row if isinstance(row, tuple) else (row['name'], row['description']))
                    service_context = f"Услуга: {name}. Описание: {desc or ''}"
            else:
                # выбрать случайную услугу пользователя
                cur.execute(
                    "SELECT name, description FROM userservices WHERE user_id = %s ORDER BY RANDOM() LIMIT 1",
                    (user_data['user_id'],),
                )
                row = cur.fetchone()
                if row:
                    name, desc = (row if isinstance(row, tuple) else (row['name'], row['description']))
                    service_context = f"Услуга: {name}. Описание: {desc or ''}"

        if use_transaction:
            if selected_transaction_id:
                # Получаем транзакцию
                cur.execute("""
                    SELECT transaction_date, amount, services, notes, client_type
                    FROM FinancialTransactions
                    WHERE id = %s AND user_id = %s
                """, (selected_transaction_id, user_data['user_id']))
                row = cur.fetchone()
                if row:
                    tx_date, amount, services_raw, notes, client_type = row
                    services_list = []
                    if services_raw:
                        try:
                            services_list = json.loads(services_raw) if isinstance(services_raw, str) else services_raw
                            if not isinstance(services_list, list):
                                services_list = []
                        except Exception:
                            services_list = []

                    services_str = ', '.join(services_list) if services_list else 'Услуги'
                    transaction_context = f"Выполнена работа: {services_str}. Дата: {tx_date}. Сумма: {amount}₽. {notes if notes else ''}"
            else:
                # Выбираем последнюю транзакцию
                cur.execute("""
                    SELECT transaction_date, amount, services, notes
                    FROM financialtransactions
                    WHERE user_id = %s
                    ORDER BY transaction_date DESC, created_at DESC
                    LIMIT 1
                """, (user_data['user_id'],))
                row = cur.fetchone()
                if row:
                    tx_date, amount, services_raw, notes = row
                    services_list = []
                    if services_raw:
                        try:
                            services_list = json.loads(services_raw) if isinstance(services_raw, str) else services_raw
                            if not isinstance(services_list, list):
                                services_list = []
                        except Exception:
                            services_list = []

                    services_str = ', '.join(services_list) if services_list else 'Услуги'
                    transaction_context = f"Выполнена работа: {services_str}. Дата: {tx_date}. Сумма: {amount}₽. {notes if notes else ''}"

        # Подтянем примеры новостей пользователя (до 5)
        news_examples = ""
        try:
            from core.db_helpers import ensure_user_examples_table
            ensure_user_examples_table(cur)
            cur.execute(
                "SELECT example_text FROM userexamples WHERE user_id = %s AND example_type = 'news' ORDER BY created_at DESC LIMIT 5",
                (user_data['user_id'],),
            )
            r = cur.fetchall()
            ex = [row[0] if isinstance(row, tuple) else row['example_text'] for row in r]
            if ex:
                news_examples = "\n".join(ex)
        except Exception:
            news_examples = ""

        # Получаем промпт из БД или используем дефолтный
        # ВАЖНО: default_prompt должен быть шаблоном с плейсхолдерами, а не f-string!
        default_prompt = """Ты - маркетолог для локального бизнеса. Сгенерируй новость для публикации на картах (Google, Яндекс).
Требования: до 1500 символов, можно использовать 2-3 эмодзи (не переборщи), без хештегов, без оценочных суждений, без упоминания конкурентов. Стиль - информативный и дружелюбный.
Write all generated text in {language_name}.
Верни СТРОГО JSON: {{"news": "текст новости"}}

Контекст услуги (может отсутствовать): {service_context}
Контекст выполненной работы/транзакции (может отсутствовать): {transaction_context}
Контекст бизнеса: {business_context}
Ограничения фактов: {forbidden_industry_examples}
Если указан контекст услуги, главная тема новости обязана быть именно эта услуга. Не пиши о платформе LocalOS, автоматизации, партнёрских программах, материнской точке сети или обзорных визитах, если этого нет в контексте услуги.
Свободная информация (может отсутствовать): {raw_info}
Если уместно, ориентируйся на стиль этих примеров (если они есть):
{news_examples}"""

        prompt_template = get_prompt_from_db('news_generation', default_prompt)

        # Логируем тип и значение prompt_template
        print(f"🔍 DEBUG news_generate: prompt_template type = {type(prompt_template)}", flush=True)
        print(f"🔍 DEBUG news_generate: prompt_template (первые 200 символов) = {str(prompt_template)[:200] if prompt_template else 'None'}", flush=True)

        # Убеждаемся, что prompt_template - это строка
        if not isinstance(prompt_template, str):
            print(f"⚠️ prompt_template не строка: {type(prompt_template)} = {prompt_template}", flush=True)
            prompt_template = default_prompt
        else:
            # Принудительно преобразуем в строку (на случай, если это bytes или что-то еще)
            try:
                prompt_template = str(prompt_template)
            except Exception as conv_err:
                print(f"⚠️ Ошибка преобразования prompt_template в строку: {conv_err}", flush=True)
                prompt_template = default_prompt

        # Финальная проверка
        if not isinstance(prompt_template, str):
            print(f"❌ prompt_template всё ещё не строка после преобразования: {type(prompt_template)}", flush=True)
            prompt_template = default_prompt

        # Принудительно преобразуем в обычную строку Python (не bytes, не специальные типы)
        try:
            if isinstance(prompt_template, bytes):
                prompt_template = prompt_template.decode('utf-8')
            else:
                prompt_template = str(prompt_template)
        except Exception as conv_err:
            print(f"⚠️ Ошибка финального преобразования prompt_template: {conv_err}", flush=True)
            prompt_template = default_prompt

        # Форматируем промпт с обработкой ошибок
        try:
            # Преобразуем все аргументы в строки для безопасности
            prompt = prompt_template.format(
                language_name=str(language_name),
                service_context=str(service_context),
                transaction_context=str(transaction_context),
                business_context=str(business_context),
                forbidden_industry_examples=str(forbidden_industry_examples),
                raw_info=str(raw_info[:800]),
                news_examples=str(news_examples)
            )
        except (KeyError, AttributeError, ValueError, TypeError) as e:
            print(f"⚠️ Ошибка форматирования промпта: {e}. Используем default_prompt", flush=True)
            import traceback
            traceback.print_exc()
            # Используем default_prompt как fallback
            prompt = default_prompt.format(
                language_name=str(language_name),
                service_context=str(service_context),
                transaction_context=str(transaction_context),
                business_context=str(business_context),
                forbidden_industry_examples=str(forbidden_industry_examples),
                raw_info=str(raw_info[:800]),
                news_examples=str(news_examples)
        )

        prompt = (
            f"{business_context}\n"
            f"{forbidden_industry_examples}\n"
            f"Рабочие паттерны индустрии для новости:\n{industry_pattern_context}\n"
            "Пиши только о фактах, которые совместимы с контекстом бизнеса выше.\n\n"
            "Если новость генерируется по услуге, не используй описание сайта, описание LocalOS, материнской точки сети, партнёрских программ или автоматизации как тему публикации.\n\n"
            f"{prompt}"
        )

        result = _analyze_news_text_with_fallback(
            prompt,
            business_name=business_name,
            language_code=language,
            service_text=service_context,
            transaction_text=transaction_context,
            raw_text=raw_info[:800],
            mode=content_mode,
            social_post_format=social_format,
            business_id_value=business_id,
            user_id_value=user_data['user_id'],
        )

        # ВАЖНО: analyze_text_with_gigachat всегда возвращает строку, не словарь
        print(f"🔍 DEBUG news_generate: result type = {type(result)}")
        print(f"🔍 DEBUG news_generate: result = {result[:200] if isinstance(result, str) else result}")

        # Обрабатываем результат - analyze_text_with_gigachat возвращает строку
        if isinstance(result, dict):
            # Если словарь (на всякий случай), проверяем наличие ошибки
            if 'error' in result:
                db.close()
                return jsonify({"error": result['error']}), 500
            generated_text = result.get('news') or result.get('text') or json.dumps(result, ensure_ascii=False)
        elif not isinstance(result, str):
            # Если не строка и не словарь, конвертируем в строку
            generated_text = str(result)
        else:
            # Если строка, пробуем распарсить как JSON
            generated_text = result
            parsed_result = None
            try:
                # Ищем JSON объект в строке
                start_idx = result.find('{')
                end_idx = result.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = result[start_idx:end_idx]
                    parsed_result = json.loads(json_str)
            except json.JSONDecodeError:
                # Если не JSON (например, кавычки внутри), пробуем регулярку/ручной парсинг
                try:
                    import re
                    # Ищем pattern: "news": "..."
                    # Используем non-greedy match для содержимого, но так как внутри могут быть кавычки,
                    # это сложно. Попробуем взять все между первыми и последними кавычками значения.
                    match = re.search(r'"news"\s*:\s*"(.*)"\s*\}', result, re.DOTALL)
                    if match:
                        generated_text = match.group(1)
                        # Экранированные кавычки возвращаем обратно, если они были правильно экранированы
                        # Но скорее всего проблема в неэкранированных.
                        # В простом случае просто вернем то что нашли.
                        parsed_result = {"news": generated_text}
                except Exception:
                    pass

            if isinstance(parsed_result, dict):
                # Проверяем наличие ошибки
                if 'error' in parsed_result:
                    db.close()
                    return jsonify({"error": parsed_result['error']}), 500

                # Используем явную проверку ключей, чтобы пустая строка не вызывала фолбэк
                if 'news' in parsed_result:
                    generated_text = parsed_result['news']
                elif 'text' in parsed_result:
                    generated_text = parsed_result['text']
                else:
                    # Если ключей нет, но это словарь - странно, но оставим result или json dump
                    pass

        generated_text = _clean_generated_news_text(generated_text)

        # Проверяем, что generated_text не пустой
        if not generated_text or not generated_text.strip():
            db.close()
            return jsonify({"error": "Пустой результат генерации"}), 500

        if service_context and (
            _news_text_has_demo_platform_drift(generated_text)
            or not _news_text_has_service_anchor(generated_text, service_context)
        ):
            generated_text = _service_focused_news_fallback(
                business_name=business_name,
                service_context=service_context,
                language_code=language,
            )

        business_identity_text = f"{business_name} {business_type_context} {business_categories}".lower()
        generated_text_lower = str(generated_text or "").lower()
        is_fuel_station = any(marker in business_identity_text for marker in ["азс", "лукойл", "заправ"])
        forbidden_for_fuel_station = [
            "пекарн",
            "булоч",
            "круассан",
            "торт",
            "выпеч",
            "салон красоты",
            "стриж",
            "окрашив",
            "медицин",
            "косметолог",
        ]
        if is_fuel_station and any(term in generated_text_lower for term in forbidden_for_fuel_station):
            if language == "ru":
                generated_text = (
                    f"Новость компании: {business_name} обновляет информацию на картах, чтобы водителям было проще "
                    "быстро найти ближайшую АЗС, проверить адрес точки и выбрать удобный маршрут. "
                    "Актуальные данные по конкретной станции смотрите в карточке на карте."
                )
            else:
                generated_text = (
                    f"Business update: {business_name} keeps map information up to date so drivers can find the nearest fuel station, "
                    "check the address, and choose a convenient route. See the specific map listing for current details."
                )

        if _news_context_is_cultural_space(business_identity_text) and _news_text_has_school_hallucination(generated_text):
            if language == "ru":
                generated_text = (
                    f"{business_name} — культурный центр: концерты, лекции, стендап, мастер-классы и события, "
                    "которые можно выбрать по афише. Актуальное расписание, подробности и запись можно уточнить "
                    "по контактам в карточке."
                )
            else:
                generated_text = (
                    f"{business_name} is a cultural venue with concerts, lectures, stand-up, workshops, and events. "
                    "Check the listing contacts for the current schedule, details, and booking."
                )

        news_id = str(uuid.uuid4())
        prompt_key = "news_social_generation" if content_mode == "social" else "news_generation"
        prompt_version = "v1"
        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id') or data.get('business_id'))
        if active_news_patterns:
            record_industry_pattern_impact_event(
                db.conn,
                active_news_patterns,
                industry_key=industry_key,
                pattern_type="news",
                business_id=business_id or "",
                user_id=user_data['user_id'],
                source="news_generate",
                event_type="applied",
                result_status="used_in_prompt",
                metrics={"content_mode": content_mode, "source_has_context": bool(service_context or transaction_context or raw_info)},
            )
            news_impact_metrics = build_pattern_impact_metrics(
                {"generated_text": generated_text},
                "news",
                industry_key=industry_key,
                source_text=f"{service_context} {transaction_context} {raw_info}",
            )
            record_industry_pattern_impact_event(
                db.conn,
                active_news_patterns,
                industry_key=industry_key,
                pattern_type="news",
                business_id=business_id or "",
                user_id=user_data['user_id'],
                source="news_generate",
                event_type="result",
                result_status="needs_review" if int(news_impact_metrics.get("needs_review") or 0) > 0 else "good",
                metrics=news_impact_metrics,
            )
        has_usernews_business_id = _table_has_column(cur, "usernews", "business_id")
        if has_usernews_business_id:
            cur.execute(
                """
                INSERT INTO usernews (
                    id, user_id, business_id, service_id, source_text, generated_text, original_generated_text,
                    edited_before_approve, prompt_key, prompt_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, FALSE, %s, %s)
                """,
                (
                    news_id,
                    user_data['user_id'],
                    business_id,
                    selected_service_id,
                    raw_info,
                    generated_text,
                    generated_text,
                    prompt_key,
                    prompt_version,
                )
            )
        else:
            cur.execute(
                """
                INSERT INTO usernews (
                    id, user_id, service_id, source_text, generated_text, original_generated_text,
                    edited_before_approve, prompt_key, prompt_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, FALSE, %s, %s)
                """,
                (
                    news_id,
                    user_data['user_id'],
                    selected_service_id,
                    raw_info,
                    generated_text,
                    generated_text,
                    prompt_key,
                    prompt_version,
                )
            )
        db.conn.commit()
        db.close()

        record_ai_learning_event(
            capability="news.generate",
            event_type="generated",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=business_id,
            prompt_key=prompt_key,
            prompt_version=prompt_version,
            draft_text=generated_text,
            metadata={
                "content_mode": content_mode,
                "social_format": social_format,
                "ab_mode": ab_mode,
                "news_id": news_id,
            },
        )

        return jsonify({"success": True, "news_id": news_id, "generated_text": generated_text})
    except Exception as e:
        print(f"❌ Ошибка генерации новости: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/news/approve', methods=['POST', 'OPTIONS'])
def news_approve():
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
        news_id = data.get('news_id')
        if not news_id:
            return jsonify({"error": "news_id обязателен"}), 400

        db = DatabaseManager()
        cur = db.conn.cursor()
        # ensure table exists
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS UserNews (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                service_id TEXT,
                source_text TEXT,
                generated_text TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_usernews_learning_columns(cur)
        cur.execute(
            """
            SELECT id, service_id, generated_text, original_generated_text, edited_before_approve, prompt_key, prompt_version
            FROM usernews
            WHERE id = %s AND user_id = %s
            """,
            (news_id, user_data['user_id']),
        )
        current_row = cur.fetchone()
        if not current_row:
            db.close()
            return jsonify({"error": "Новость не найдена"}), 404
        current_data = _row_to_dict(cur, current_row)
        cur.execute("UPDATE usernews SET approved = 1 WHERE id = %s AND user_id = %s", (news_id, user_data['user_id']))
        if cur.rowcount == 0:
            db.close()
            return jsonify({"error": "Новость не найдена"}), 404
        db.conn.commit()
        db.close()
        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id'))
        record_ai_learning_event(
            capability="news.generate",
            event_type="accepted",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=business_id,
            accepted=True,
            edited_before_accept=bool(current_data.get("edited_before_approve")),
            prompt_key=str(current_data.get("prompt_key") or "news_generation"),
            prompt_version=str(current_data.get("prompt_version") or "v1"),
            draft_text=str(current_data.get("original_generated_text") or current_data.get("generated_text") or ""),
            final_text=str(current_data.get("generated_text") or ""),
            metadata={"news_id": news_id},
        )
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка утверждения новости: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news/list', methods=['GET', 'OPTIONS'])
def news_list():
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
        cur = db.conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS UserNews (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                service_id TEXT,
                source_text TEXT,
                generated_text TEXT NOT NULL,
                approved INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        _ensure_usernews_learning_columns(cur)
        selected_business_id = request.args.get('business_id')
        has_usernews_business_id = _table_has_column(cur, "usernews", "business_id")
        if has_usernews_business_id and selected_business_id:
            cur.execute(
                """
                SELECT id, business_id, service_id, source_text, generated_text, original_generated_text, edited_before_approve, approved, created_at
                FROM usernews
                WHERE user_id = %s AND business_id = %s
                ORDER BY created_at DESC
                """,
                (user_data['user_id'], selected_business_id),
            )
        else:
            cur.execute(
                """
                SELECT id, business_id, service_id, source_text, generated_text, original_generated_text, edited_before_approve, approved, created_at
                FROM usernews
                WHERE user_id = %s
                ORDER BY created_at DESC
                """,
                (user_data['user_id'],),
            )
        rows = cur.fetchall()
        db.close()
        items = []
        for row in rows:
            if isinstance(row, tuple):
                items.append({
                    "id": row[0], "business_id": row[1], "service_id": row[2], "source_text": row[3],
                    "generated_text": row[4],
                    "original_generated_text": row[5],
                    "edited_before_approve": bool(row[6]),
                    "approved": bool(row[7]),
                    "created_at": row[8]
                })
            else:
                items.append({
                    "id": row['id'], "business_id": row.get('business_id'), "service_id": row['service_id'], "source_text": row['source_text'],
                    "generated_text": row['generated_text'],
                    "original_generated_text": row.get('original_generated_text'),
                    "edited_before_approve": bool(row.get('edited_before_approve')),
                    "approved": bool(row['approved']),
                    "created_at": row['created_at']
                })
        return jsonify({"success": True, "news": items})
    except Exception as e:
        print(f"❌ Ошибка получения списка новостей: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news/update', methods=['POST', 'OPTIONS'])
def news_update():
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
        news_id = data.get('news_id'); text = (data.get('text') or '').strip()
        if not news_id or not text:
            return jsonify({"error": "news_id и text обязательны"}), 400
        db = DatabaseManager(); cur = db.conn.cursor()
        _ensure_usernews_learning_columns(cur)
        selected_business_id = data.get('business_id') or request.args.get('business_id')
        has_usernews_business_id = _table_has_column(cur, "usernews", "business_id")
        update_select_query = """
            SELECT generated_text, original_generated_text, prompt_key, prompt_version
            FROM usernews
            WHERE id = %s AND user_id = %s
        """
        update_select_params = [news_id, user_data['user_id']]
        if has_usernews_business_id and selected_business_id:
            update_select_query += " AND business_id = %s"
            update_select_params.append(selected_business_id)
        cur.execute(update_select_query, tuple(update_select_params))
        existing_row = cur.fetchone()
        if not existing_row:
            db.close(); return jsonify({"error": "Новость не найдена"}), 404
        existing = _row_to_dict(cur, existing_row)
        original_generated_text = str(existing.get("original_generated_text") or existing.get("generated_text") or "")
        edited_before_approve = _normalize_text_for_semantic_compare(text) != _normalize_text_for_semantic_compare(original_generated_text)
        update_query = """
            UPDATE usernews
            SET generated_text = %s,
                edited_before_approve = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND user_id = %s
        """
        update_params = [text, edited_before_approve, news_id, user_data['user_id']]
        if has_usernews_business_id and selected_business_id:
            update_query += " AND business_id = %s"
            update_params.append(selected_business_id)
        cur.execute(update_query, tuple(update_params))
        if cur.rowcount == 0:
            db.close(); return jsonify({"error": "Новость не найдена"}), 404
        db.conn.commit(); db.close()
        business_id = get_business_id_from_user(user_data['user_id'], selected_business_id)
        record_ai_learning_event(
            capability="news.generate",
            event_type="edited",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=business_id,
            accepted=None,
            edited_before_accept=edited_before_approve,
            prompt_key=str(existing.get("prompt_key") or "news_generation"),
            prompt_version=str(existing.get("prompt_version") or "v1"),
            draft_text=original_generated_text,
            final_text=text,
            metadata={"news_id": news_id},
        )
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка обновления новости: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news/delete', methods=['POST', 'OPTIONS'])
def news_delete():
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
        news_id = data.get('news_id')
        if not news_id:
            return jsonify({"error": "news_id обязателен"}), 400

        db = DatabaseManager()
        cur = db.conn.cursor()
        _ensure_usernews_learning_columns(cur)
        selected_business_id = data.get('business_id') or request.args.get('business_id')
        has_usernews_business_id = _table_has_column(cur, "usernews", "business_id")
        delete_select_query = """
            SELECT id, approved, generated_text, original_generated_text, prompt_key, prompt_version
            FROM usernews
            WHERE id = %s AND user_id = %s
        """
        delete_select_params = [news_id, user_data['user_id']]
        if has_usernews_business_id and selected_business_id:
            delete_select_query += " AND business_id = %s"
            delete_select_params.append(selected_business_id)
        cur.execute(delete_select_query, tuple(delete_select_params))
        existing_row = cur.fetchone()
        if not existing_row:
            db.close()
            return jsonify({"error": "Новость не найдена"}), 404
        existing = _row_to_dict(cur, existing_row)
        delete_query = "DELETE FROM usernews WHERE id = %s AND user_id = %s"
        delete_params = [news_id, user_data['user_id']]
        if has_usernews_business_id and selected_business_id:
            delete_query += " AND business_id = %s"
            delete_params.append(selected_business_id)
        cur.execute(delete_query, tuple(delete_params))
        deleted = cur.rowcount
        db.conn.commit()
        db.close()

        if deleted == 0:
            return jsonify({"error": "Новость не найдена"}), 404
        if not bool(existing.get("approved")):
            business_id = get_business_id_from_user(user_data['user_id'], selected_business_id)
            record_ai_learning_event(
                capability="news.generate",
                event_type="rejected",
                intent="operations",
                user_id=user_data['user_id'],
                business_id=business_id,
                rejected=True,
                prompt_key=str(existing.get("prompt_key") or "news_generation"),
                prompt_version=str(existing.get("prompt_version") or "v1"),
                draft_text=str(existing.get("original_generated_text") or existing.get("generated_text") or ""),
                final_text=None,
                metadata={"news_id": news_id, "via": "delete"},
            )
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка удаления новости: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/review-examples', methods=['GET', 'POST', 'OPTIONS'])
def review_examples():
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

        db = DatabaseManager(); cur = db.conn.cursor()
        from core.db_helpers import ensure_user_examples_table
        ensure_user_examples_table(cur)

        if request.method == 'GET':
            cur.execute(
                "SELECT id, example_text, created_at FROM userexamples WHERE user_id = %s AND example_type = 'review' ORDER BY created_at DESC",
                (user_data['user_id'],),
            )
            rows = cur.fetchall(); db.close()
            items = []
            for row in rows:
                rd = _row_to_dict(cur, row) if row else {}
                items.append({"id": rd.get("id"), "text": rd.get("example_text"), "created_at": rd.get("created_at")})
            return jsonify({"success": True, "examples": items})

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close(); return jsonify({"error": "Текст примера обязателен"}), 400
        cur.execute("SELECT COUNT(*) AS cnt FROM userexamples WHERE user_id = %s AND example_type = 'review'", (user_data['user_id'],))
        cnt_row = cur.fetchone()
        cnt_data = _row_to_dict(cur, cnt_row) if cnt_row else {}
        cnt = cnt_data.get("cnt", 0) or 0
        if cnt >= 5:
            db.close(); return jsonify({"error": "Максимум 5 примеров"}), 400
        ex_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO userexamples (id, user_id, example_type, example_text) VALUES (%s, %s, 'review', %s)",
            (ex_id, user_data['user_id'], text),
        )
        db.conn.commit(); db.close()
        return jsonify({"success": True, "id": ex_id})
    except Exception as e:
        print(f"❌ Ошибка примеров отзывов: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/review-examples/<example_id>', methods=['DELETE', 'OPTIONS'])
def review_examples_delete(example_id: str):
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
        db = DatabaseManager(); cur = db.conn.cursor()
        cur.execute(
            "DELETE FROM userexamples WHERE id = %s AND user_id = %s AND example_type = 'review'",
            (example_id, user_data['user_id']),
        )
        deleted = cur.rowcount
        db.conn.commit(); db.close()
        if deleted == 0:
            return jsonify({"error": "Пример не найден"}), 404
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка удаления примера отзывов: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news-examples', methods=['GET', 'POST', 'OPTIONS'])
def news_examples():
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

        db = DatabaseManager(); cur = db.conn.cursor()
        from core.db_helpers import ensure_user_examples_table
        ensure_user_examples_table(cur)

        if request.method == 'GET':
            cur.execute(
                "SELECT id, example_text, created_at FROM userexamples WHERE user_id = %s AND example_type = 'news' ORDER BY created_at DESC",
                (user_data['user_id'],),
            )
            rows = cur.fetchall(); db.close()
            items = []
            for row in rows:
                if isinstance(row, tuple):
                    items.append({"id": row[0], "text": row[1], "created_at": row[2]})
                else:
                    items.append({"id": row['id'], "text": row['example_text'], "created_at": row['created_at']})
            return jsonify({"success": True, "examples": items})

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close(); return jsonify({"error": "Текст примера обязателен"}), 400
        cur.execute("SELECT COUNT(*) AS cnt FROM userexamples WHERE user_id = %s AND example_type = 'news'", (user_data['user_id'],))
        cnt_row = cur.fetchone()
        cnt_data = _row_to_dict(cur, cnt_row) if cnt_row else {}
        cnt = cnt_data.get("cnt", 0) or 0
        if cnt >= 5:
            db.close(); return jsonify({"error": "Максимум 5 примеров"}), 400
        ex_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO userexamples (id, user_id, example_type, example_text) VALUES (%s, %s, 'news', %s)",
            (ex_id, user_data['user_id'], text),
        )
        db.conn.commit(); db.close()
        return jsonify({"success": True, "id": ex_id})
    except Exception as e:
        print(f"❌ Ошибка примеров новостей: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news-examples/<example_id>', methods=['DELETE', 'OPTIONS'])
def news_examples_delete(example_id: str):
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
        db = DatabaseManager(); cur = db.conn.cursor()
        cur.execute("DELETE FROM userexamples WHERE id = %s AND user_id = %s AND example_type = 'news'", (example_id, user_data['user_id']))
        deleted = cur.rowcount
        db.conn.commit(); db.close()
        if deleted == 0:
            return jsonify({"error": "Пример не найден"}), 404
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка удаления примера новостей: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/news/ab-mode/availability', methods=['GET', 'OPTIONS'])
def news_ab_mode_availability():
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

        is_superadmin = bool(user_data.get("is_superadmin")) if isinstance(user_data, dict) else False
        is_test_mode = os.getenv("NEWS_AB_TEST_MODE", "1").strip().lower() in ("1", "true", "yes", "on")
        return jsonify({
            "success": True,
            "allowed": bool(is_superadmin and is_test_mode),
            "is_superadmin": is_superadmin,
            "test_mode": is_test_mode,
        })
    except Exception as e:
        print(f"❌ Ошибка проверки доступности news AB mode: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/reviews/reply', methods=['POST', 'OPTIONS'])
def reviews_reply():
    """Сгенерировать короткий вежливый ответ на отзыв в заданном тоне."""
    import sys
    print(f"🔍 Начало обработки запроса /api/reviews/reply", file=sys.stderr, flush=True)
    print(f"🔍 Начало обработки запроса /api/reviews/reply", flush=True)
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

        # Проверяем, что user_data - это словарь
        if not isinstance(user_data, dict):
            print(f"⚠️ user_data не словарь: {type(user_data)} = {user_data}", flush=True)
            return jsonify({"error": "Ошибка авторизации: неверный формат данных пользователя"}), 401

        data = request.get_json() or {}
        review_text = (data.get('review') or '').strip()
        tone = (data.get('tone') or 'профессиональный').strip()

        # Язык ответа: получаем из запроса или из профиля пользователя
        requested_language = data.get('language')
        language = get_user_language(user_data['user_id'], requested_language)
        language_names = {
            'ru': 'Russian',
            'en': 'English',
            'es': 'Spanish',
            'de': 'German',
            'fr': 'French',
            'it': 'Italian',
            'pt': 'Portuguese',
            'zh': 'Chinese'
        }
        language_name = language_names.get(language, 'Russian')
        if not review_text:
            return jsonify({"error": "Не передан текст отзыва"}), 400
        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id'))
        review_industry_key = "local_business"
        active_reply_patterns: list[dict] = []
        review_industry_context = format_industry_pattern_prompt("local_business", mode="review_reply")
        business_display_name = ""
        if business_id:
            try:
                db_profile = DatabaseManager()
                cur_profile = db_profile.conn.cursor()
                cur_profile.execute(
                    """
                    SELECT name, business_type, industry, categories
                    FROM businesses
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (business_id,),
                )
                profile_row = cur_profile.fetchone()
                profile_data = _row_to_dict(cur_profile, profile_row) if profile_row else {}
                business_display_name = str(profile_data.get("name") or "").strip()
                review_industry_key = detect_industry_key(
                    business_name=profile_data.get("name"),
                    business_type=profile_data.get("business_type"),
                    industry=profile_data.get("industry"),
                    categories=profile_data.get("categories"),
                    service_text=review_text,
                )
                review_industry_context = format_industry_pattern_prompt(review_industry_key, mode="review_reply")
                active_reply_patterns = load_active_industry_patterns(db_profile.conn, review_industry_key, "review_reply")
                active_reply_pattern_text = format_loaded_active_industry_patterns(active_reply_patterns)
                if active_reply_pattern_text:
                    review_industry_context += f"\n{active_reply_pattern_text}"
                db_profile.close()
            except Exception:
                review_industry_context = format_industry_pattern_prompt("local_business", mode="review_reply")

        # Подтянем примеры ответов пользователя (до 5)
        # Сначала проверяем, переданы ли примеры в запросе
        examples_from_request = data.get('examples', [])
        examples_text = ""

        if examples_from_request and isinstance(examples_from_request, list):
            # Используем примеры из запроса
            examples_text = "\n".join(examples_from_request[:5])
        else:
            # Иначе загружаем из БД
            try:
                db = DatabaseManager()
                cur = db.conn.cursor()
                from core.db_helpers import ensure_user_examples_table
                ensure_user_examples_table(cur)
                cur.execute(
                    "SELECT example_text FROM userexamples WHERE user_id = %s AND example_type = 'review' ORDER BY created_at DESC LIMIT 5",
                    (user_data['user_id'],),
                )
                rows = cur.fetchall(); db.close()
                examples = []
                for row in rows:
                    if isinstance(row, tuple) and len(row) > 0:
                        examples.append(row[0])
                    elif isinstance(row, dict):
                        examples.append(row.get('example_text', ''))
                    elif hasattr(row, '__getitem__'):
                        try:
                            examples.append(row[0] if len(row) > 0 else '')
                        except (TypeError, KeyError):
                            try:
                                examples.append(row['example_text'])
                            except (TypeError, KeyError):
                                pass
                if examples:
                    examples_text = "\n".join(examples)
            except Exception:
                examples_text = ""

        # Подтягиваем SEO-ключи (Top-10), чтобы ответы были ближе к целевому семантическому ядру
        seo_keywords_list = []
        seo_keywords_top10 = ""
        if business_id:
            try:
                from core.seo_keywords import collect_ranked_keywords
                db_kw = DatabaseManager()
                cur_kw = db_kw.conn.cursor()
                ranked = collect_ranked_keywords(
                    cur_kw,
                    business_id=business_id,
                    user_id=user_data['user_id'],
                    limit=10,
                )
                seo_keywords_list = [str((it or {}).get("keyword", "")).strip() for it in (ranked or {}).get("items", [])]
                seo_keywords_list = [kw for kw in seo_keywords_list if kw]
                seo_keywords_top10 = ", ".join(seo_keywords_list[:10])
                db_kw.close()
            except Exception as kw_err:
                print(f"⚠️ reviews_reply: не удалось загрузить SEO-ключи: {kw_err}", flush=True)

        # Получаем промпт из БД или используем дефолтный
        # ВАЖНО: default_prompt должен быть шаблоном с плейсхолдерами, а не f-string!
        default_prompt_template = """Ты - вежливый менеджер салона красоты. Сгенерируй КОРОТКИЙ (до 250 символов) ответ на отзыв клиента.
Тон: {tone}. Запрещены оценки, оскорбления, обсуждение конкурентов, лишние рассуждения. Только благодарность/сочувствие/решение.
Write the reply in {language_name}.
Если уместно, ориентируйся на стиль этих примеров (если они есть):
{examples_text}
SEO Wordstat ключи (если есть): {seo_keywords}
Top-10 SEO ключей: {seo_keywords_top10}
Обязательные правила качества:
- Не возвращай Markdown, кодовые блоки, пояснения или текст вне JSON.
- Ответ должен быть готовым текстом для владельца бизнеса, без технических символов.
- Упомяни одну конкретную деталь из отзыва, если она есть.
- Не пиши общий ответ вида "Спасибо за отзыв, будем рады видеть вас снова", если в отзыве есть факты.
Верни СТРОГО JSON: {{"reply": "текст ответа"}}

Отзыв клиента: {review_text}"""

        prompt_template = get_prompt_from_db('review_reply', default_prompt_template)

        # Логируем тип и значение prompt_template
        print(f"🔍 DEBUG reviews_reply: prompt_template type = {type(prompt_template)}", flush=True)
        print(f"🔍 DEBUG reviews_reply: prompt_template (первые 200 символов) = {str(prompt_template)[:200] if prompt_template else 'None'}", flush=True)

        # Убеждаемся, что prompt_template - это строка
        if not isinstance(prompt_template, str):
            print(f"⚠️ prompt_template не строка: {type(prompt_template)} = {prompt_template}", flush=True)
            prompt_template = default_prompt_template
        else:
            # Принудительно преобразуем в строку (на случай, если это bytes или что-то еще)
            try:
                prompt_template = str(prompt_template)
            except Exception as conv_err:
                print(f"⚠️ Ошибка преобразования prompt_template в строку: {conv_err}", flush=True)
                prompt_template = default_prompt_template

        # Финальная проверка
        if not isinstance(prompt_template, str):
            print(f"❌ prompt_template всё ещё не строка после преобразования: {type(prompt_template)}", flush=True)
            prompt_template = default_prompt_template

        # Принудительно преобразуем в обычную строку Python (не bytes, не специальные типы)
        try:
            if isinstance(prompt_template, bytes):
                prompt_template = prompt_template.decode('utf-8')
            else:
                prompt_template = str(prompt_template)
        except Exception as conv_err:
            print(f"⚠️ Ошибка финального преобразования prompt_template: {conv_err}", flush=True)
            prompt_template = default_prompt_template

        # Убеждаемся, что это действительно строка
        if not isinstance(prompt_template, str):
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: prompt_template не строка: {type(prompt_template)}", flush=True)
            prompt_template = default_prompt_template

        # Логируем все аргументы перед format
        print(f"🔍 DEBUG reviews_reply: tone type = {type(tone)}, value = {tone}", flush=True)
        print(f"🔍 DEBUG reviews_reply: language_name type = {type(language_name)}, value = {language_name}", flush=True)
        print(f"🔍 DEBUG reviews_reply: examples_text type = {type(examples_text)}, value (первые 100) = {str(examples_text)[:100] if examples_text else 'None'}", flush=True)
        print(f"🔍 DEBUG reviews_reply: review_text type = {type(review_text)}, value (первые 100) = {str(review_text)[:100] if review_text else 'None'}", flush=True)

        # Принудительно преобразуем все аргументы в строки
        tone_str = str(tone) if tone else ''
        language_name_str = str(language_name) if language_name else 'Russian'
        examples_text_str = str(examples_text) if examples_text else ''
        review_text_str = str(review_text[:1000]) if review_text else ''

        try:
            prompt = _format_template_with_literal_json_fallback(
                prompt_template,
                {
                    "tone": tone_str,
                    "language_name": language_name_str,
                    "examples_text": examples_text_str,
                    "review_text": review_text_str,
                    "seo_keywords": seo_keywords_top10,
                    "seo_keywords_top10": seo_keywords_top10,
                    "business_name": business_display_name,
                },
            )
        except (KeyError, ValueError, TypeError) as format_err:
            print(f"⚠️ Ошибка форматирования промпта: {format_err}, type: {type(format_err)}", flush=True)
            import traceback
            traceback.print_exc()
            # Используем default_prompt_template как fallback
            prompt = _format_template_with_literal_json_fallback(
                default_prompt_template,
                {
                    "tone": tone_str,
                    "language_name": language_name_str,
                    "examples_text": examples_text_str,
                    "review_text": review_text_str,
                    "seo_keywords": seo_keywords_top10,
                    "seo_keywords_top10": seo_keywords_top10,
                    "business_name": business_display_name,
                },
            )
        prompt = (
            "Рабочие паттерны индустрии для ответа на отзыв:\n"
            f"{review_industry_context}\n\n"
            "Финальный ответ должен пройти проверку: чистый текст внутри JSON, одна конкретная деталь из отзыва, без шаблонной воды.\n\n"
            f"{prompt}"
        )
        # Логируем промпт для отладки
        print(f"🔍 DEBUG reviews_reply: prompt (первые 500 символов) = {prompt[:500]}")
        print(f"🔍 DEBUG reviews_reply: review_text = {review_text[:200] if review_text else 'ПУСТО'}")
        print(f"🔍 DEBUG reviews_reply: examples_text (первые 200 символов) = {examples_text[:200] if examples_text else 'ПУСТО'}")

        result_text = analyze_text_with_gigachat(
            prompt,
            task_type="review_reply",
            business_id=business_id,
            user_id=user_data['user_id']
        )

        # ВАЖНО: analyze_text_with_gigachat всегда возвращает строку
        print(f"🔍 DEBUG reviews_reply: result_text type = {type(result_text)}")
        print(f"🔍 DEBUG reviews_reply: result_text = {result_text[:200] if isinstance(result_text, str) else result_text}")

        reply_text, malformed_model_output = _extract_review_reply_from_model_result(result_text)
        if result_text is None:
            print("⚠️ result_text is None")
        if not reply_text and isinstance(result_text, dict) and result_text.get('error'):
            print(f"❌ Ошибка в результате: {result_text.get('error')}")
            return jsonify({"error": result_text.get('error', 'Ошибка генерации')}), 500
        reply_text = _normalize_review_reply_output(
            reply_text,
            review_text,
            malformed_model_output=malformed_model_output,
            language=language,
        )

        business_id = get_business_id_from_user(user_data['user_id'], request.args.get('business_id') if request else None)
        if active_reply_patterns:
            impact_db = DatabaseManager()
            record_industry_pattern_impact_event(
                impact_db.conn,
                active_reply_patterns,
                industry_key=review_industry_key,
                pattern_type="review_reply",
                business_id=business_id or "",
                user_id=user_data['user_id'],
                source="reviews_reply",
                event_type="applied",
                result_status="used_in_prompt",
                metrics={"review_length": len(str(review_text or "")), "tone": tone},
            )
            reply_impact_metrics = build_pattern_impact_metrics(
                {"reply": reply_text},
                "review_reply",
                industry_key=review_industry_key,
                source_text=review_text,
            )
            record_industry_pattern_impact_event(
                impact_db.conn,
                active_reply_patterns,
                industry_key=review_industry_key,
                pattern_type="review_reply",
                business_id=business_id or "",
                user_id=user_data['user_id'],
                source="reviews_reply",
                event_type="result",
                result_status="needs_review" if int(reply_impact_metrics.get("needs_review") or 0) > 0 else "good",
                metrics=reply_impact_metrics,
            )
            impact_db.conn.commit()
            impact_db.close()
        record_ai_learning_event(
            capability="reviews.reply",
            event_type="generated",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=business_id,
            prompt_key="review_reply",
            prompt_version="v1",
            draft_text=reply_text,
            metadata={"tone": tone, "language": language},
        )
        return jsonify({"success": True, "result": {"reply": reply_text}})
    except Exception as e:
        import sys
        import traceback
        error_msg = f"❌ Ошибка генерации ответа на отзыв: {e}"
        print(error_msg, file=sys.stderr, flush=True)
        print(error_msg, flush=True)
        traceback.print_exc(file=sys.stderr)
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/review-replies/update', methods=['POST', 'OPTIONS'])
def review_replies_update():
    """Сохранить отредактированный ответ на отзыв"""
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
        if not isinstance(data, dict):
            return jsonify({"error": "Invalid JSON"}), 400

        reply_id = data.get('replyId') or data.get('reply_id')
        reply_text = (data.get('replyText') or data.get('reply_text') or '').strip()
        generated_text = str(data.get('generatedText') or data.get('generated_text') or '').strip()
        business_id = str(data.get('business_id') or '').strip()

        if not reply_id:
            return jsonify({"error": "ID ответа обязателен"}), 400

        if not reply_text:
            return jsonify({"error": "Текст ответа обязателен"}), 400

        # Создаем таблицу для хранения ответов на отзывы, если её нет
        db = DatabaseManager()
        cursor = db.conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS userreviewreplies (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                original_review TEXT,
                reply_text TEXT NOT NULL,
                tone TEXT DEFAULT 'профессиональный',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            )
            """
        )

        # Обновляем или создаем запись
        cursor.execute(
            """
            INSERT INTO userreviewreplies (id, user_id, reply_text, updated_at)
            VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (id) DO UPDATE
            SET reply_text = EXCLUDED.reply_text,
                user_id = EXCLUDED.user_id,
                updated_at = CURRENT_TIMESTAMP
            """,
            (reply_id, user_data['user_id'], reply_text),
        )

        db.conn.commit()
        db.close()

        normalized_generated = _normalize_text_for_semantic_compare(generated_text)
        normalized_reply = _normalize_text_for_semantic_compare(reply_text)
        edited_before_accept = bool(generated_text) and normalized_generated != normalized_reply
        record_ai_learning_event(
            capability="reviews.reply",
            event_type="accepted",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=business_id if business_id else None,
            accepted=True,
            edited_before_accept=edited_before_accept,
            prompt_key="review_reply",
            prompt_version="v1",
            draft_text=generated_text or None,
            final_text=reply_text,
            metadata={"reply_id": reply_id},
        )

        return jsonify({"success": True, "message": "Ответ на отзыв сохранен"})

    except Exception as e:
        print(f"❌ Ошибка сохранения ответа на отзыв: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/services/add', methods=['POST', 'OPTIONS'])
def add_service():
    """Добавление услуги в список пользователя."""
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

        data = request.get_json()
        if not data:
            return jsonify({"error": "Данные не предоставлены"}), 400

        category = data.get('category', 'Общие услуги')
        name = data.get('name', '')
        description = data.get('description', '')
        keywords = data.get('keywords', [])
        price = data.get('price', '')
        business_id = data.get('business_id')

        if not name:
            return jsonify({"error": "Название услуги обязательно"}), 400

        db = DatabaseManager()
        cursor = db.conn.cursor()
        user_id = user_data['user_id']
        service_id = str(uuid.uuid4())

        # Проверяем, есть ли поле business_id в таблице userservices
        columns = _table_columns(cursor, "userservices")

        if 'business_id' in columns and business_id:
            cursor.execute(
                """
                INSERT INTO userservices (id, user_id, business_id, category, name, description, keywords, price, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (service_id, user_id, business_id, category, name, description, json.dumps(keywords), price),
            )
        else:
            cursor.execute(
                """
                INSERT INTO userservices (id, user_id, category, name, description, keywords, price, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """,
                (service_id, user_id, category, name, description, json.dumps(keywords), price),
            )

        db.conn.commit()
        db.close()
        return jsonify({"success": True, "message": "Услуга добавлена"})

    except Exception as e:
        print(f"❌ Ошибка добавления услуги: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/services/list-legacy', methods=['GET', 'OPTIONS'])
def get_services_legacy():
    """Получение списка услуг пользователя."""
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
        cursor = db.conn.cursor()
        user_id = user_data['user_id']

        # Получаем business_id из query параметров
        business_id = request.args.get('business_id')

        # Если передан business_id - фильтруем по нему, иначе по user_id
        if business_id:
            # Проверяем доступ к бизнесу
            owner_id = get_business_owner_id(cursor, business_id, include_active_check=True)
            if owner_id:
                if owner_id == user_id or user_data.get('is_superadmin'):
                    # Проверяем, есть ли поля optimized_description и optimized_name
                    columns = _table_columns(cursor, "userservices")
                    has_optimized_desc = 'optimized_description' in columns
                    has_optimized_name = 'optimized_name' in columns

    # Формируем SELECT с учетом наличия полей
                    select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at', 'updated_at']
                    if has_optimized_desc:
                        select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
                    if has_optimized_name:
                        select_fields.insert(select_fields.index('name') + 1, 'optimized_name')

                    select_sql = f"SELECT {', '.join(select_fields)} FROM userservices WHERE business_id = %s ORDER BY created_at DESC"
                    cursor.execute(select_sql, (business_id,))

                    user_services = []
                    rows = cursor.fetchall()
                    for r in rows:
                        rd = r if hasattr(r, "keys") else None
                        if rd is None:
                            rd = {field: r[idx] for idx, field in enumerate(select_fields) if idx < len(r)}
                        srv = {
                            "id": rd.get("id"),
                            "category": rd.get("category"),
                            "name": rd.get("name"),
                            "description": rd.get("description"),
                            "keywords": rd.get("keywords"),
                            "price": rd.get("price"),
                            "created_at": rd.get("created_at"),
                            "updated_at": (str(rd.get("updated_at")) if rd.get("updated_at") else None),
                        }
                        if has_optimized_desc:
                            srv["optimized_description"] = rd.get("optimized_description")
                        if has_optimized_name:
                            srv["optimized_name"] = rd.get("optimized_name")
                        user_services.append(srv)

                    # Получаем внешние услуги
                    external_services = []
                    cursor.execute("SELECT to_regclass('public.externalbusinessservices')")
                    if cursor.fetchone():
                        # Проверяем колонки externalbusinessservices (Postgres)
                        cursor.execute("""
                            SELECT column_name FROM information_schema.columns
                            WHERE table_schema = 'public' AND table_name = 'externalbusinessservices'
                        """)
                        ext_cols = [col['column_name'] if isinstance(col, dict) else col[0] for col in cursor.fetchall()]
                        ext_has_updated_at = 'updated_at' in ext_cols

                        query_cols = "id, name, price, description, category, created_at"
                        if ext_has_updated_at:
                            query_cols += ", updated_at"

                        cursor.execute(f"""
                            SELECT {query_cols}
                            FROM externalbusinessservices
                            WHERE business_id = %s
                        """, (business_id,))

                        for r in cursor.fetchall():
                            rd = r if hasattr(r, "keys") else None
                            if rd is None:
                                rd = {
                                    "id": r[0],
                                    "name": r[1],
                                    "price": r[2],
                                    "description": r[3],
                                    "category": r[4],
                                    "created_at": r[5],
                                    "updated_at": r[6] if ext_has_updated_at and len(r) > 6 else None,
                                }
                            srv_obj = {
                                "id": rd.get("id"),
                                "name": rd.get("name"),
                                "price": rd.get("price"),
                                "description": rd.get("description"),
                                "category": rd.get("category"),
                                "created_at": rd.get("created_at"),
                                "is_external": True,
                            }
                            val = rd.get("updated_at") if ext_has_updated_at else rd.get("created_at")
                            srv_obj["updated_at"] = str(val) if val else None
                            external_services.append(srv_obj)

                    db.close()
                    return jsonify({
                        "success": True,
                        "services": user_services,
                        "external_services": external_services
                    })
                else:
                    db.close()
                    return jsonify({"error": "Нет доступа к этому бизнесу"}), 403
            else:
                db.close()
                return jsonify({"error": "Бизнес не найден"}), 404
        else:
            # Старая логика для обратной совместимости
            # Проверяем, есть ли поля optimized_description и optimized_name
            columns = _table_columns(cursor, "userservices")
            has_optimized_desc = 'optimized_description' in columns
            has_optimized_name = 'optimized_name' in columns

            # Формируем SELECT с учетом наличия полей
            select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at']
            if has_optimized_desc:
                select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
            if has_optimized_name:
                select_fields.insert(select_fields.index('name') + 1, 'optimized_name')

            select_sql = f"SELECT {', '.join(select_fields)} FROM userservices WHERE user_id = %s ORDER BY created_at DESC"
            print(f"🔍 DEBUG get_services: SQL запрос (старая логика) = {select_sql}", flush=True)
            print(f"🔍 DEBUG get_services: select_fields = {select_fields}", flush=True)
            # Сохраняем select_fields для использования в цикле
            _select_fields = select_fields
            _has_optimized_desc = has_optimized_desc
            _has_optimized_name = has_optimized_name

            cursor.execute(select_sql, (user_id,))

        services = cursor.fetchall()
        db.close()

        result = []
        # Используем глобальные переменные, если они установлены
        try:
            has_optimized_desc = _has_optimized_desc
            has_optimized_name = _has_optimized_name
            select_fields = _select_fields
        except NameError:
            # Если не установлены (старая логика), проверяем заново
            cursor_temp = db.conn.cursor() if 'db' in locals() else None
            if cursor_temp:
                columns = _table_columns(cursor_temp, "userservices")
                has_optimized_desc = 'optimized_description' in columns
                has_optimized_name = 'optimized_name' in columns
                select_fields = ['id', 'category', 'name', 'description', 'keywords', 'price', 'created_at']
                if has_optimized_desc:
                    select_fields.insert(select_fields.index('description') + 1, 'optimized_description')
                if has_optimized_name:
                    select_fields.insert(select_fields.index('name') + 1, 'optimized_name')
            else:
                has_optimized_desc = False
                has_optimized_name = False
                select_fields = []

        for service in services:
            # ПРОСТОЕ РЕШЕНИЕ: Преобразуем Row в словарь через dict()
            # Это гарантирует правильное извлечение всех полей, включая optimized_name и optimized_description
            if hasattr(service, 'keys'):
                service_dict = dict(service)  # Преобразуем Row в dict
            else:
                # Fallback для tuple/list - создаем словарь по порядку полей
                service_dict = {field_name: service[idx] for idx, field_name in enumerate(select_fields) if idx < len(service)}

            # Парсим keywords
            raw_kw = service_dict.get('keywords')
            parsed_kw = []
            if raw_kw:
                try:
                    parsed_kw = json.loads(raw_kw)
                    if not isinstance(parsed_kw, list):
                        parsed_kw = []
                except Exception:
                    parsed_kw = [k.strip() for k in str(raw_kw).split(',') if k.strip()]
            service_dict['keywords'] = parsed_kw

            # optimized_name и optimized_description уже будут в service_dict после dict(service)
            # Дополнительная проверка не нужна, т.к. dict(service) извлекает все поля из Row

            # Логируем для отладки (только для первой услуги и для услуги с ID 3772931e-9796-475b-b439-ee1cc07b1dc9)
            service_id = service_dict.get('id')
            if len(result) == 0 or service_id == '3772931e-9796-475b-b439-ee1cc07b1dc9':
                print(f"🔍 DEBUG get_services: Услуга {service_id}", flush=True)
                print(f"🔍 DEBUG get_services: service_dict keys = {list(service_dict.keys())}", flush=True)
                print(f"🔍 DEBUG get_services: optimized_name = {service_dict.get('optimized_name')}", flush=True)
                print(f"🔍 DEBUG get_services: optimized_description = {service_dict.get('optimized_description')[:50] if service_dict.get('optimized_description') else None}...", flush=True)

            result.append(service_dict)

        return jsonify({"success": True, "services": result})

    except Exception as e:
        print(f"❌ Ошибка получения услуг: {e}")
        return jsonify({"error": str(e)}), 500
