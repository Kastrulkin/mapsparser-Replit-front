from legacy_routes import shared as _shared

globals().update(_shared.runtime_namespace)

def _review_reply_has_source_detail(reply_text: object, review_text: object) -> bool:
    reply_normalized = _normalize_text_for_semantic_compare(str(reply_text or ""))
    review_normalized = _normalize_text_for_semantic_compare(str(review_text or ""))
    if not reply_normalized or not review_normalized:
        return False
    detail_phrase = _review_reply_detail_phrase(review_text)
    if detail_phrase:
        detail_terms = [
            term
            for term in _normalize_text_for_semantic_compare(detail_phrase).split()
            if len(term) >= 5
        ]
        return any(term in reply_normalized for term in detail_terms)
    stop_words = {
        "спасибо", "отзыв", "клиент", "клиента", "демо", "яндекс", "карты",
        "очень", "ваш", "ваша", "нам", "рады", "будем", "снова",
    }
    review_terms = [
        term
        for term in review_normalized.split()
        if len(term) >= 6 and term not in stop_words
    ]
    return any(term in reply_normalized for term in review_terms[:8])

def _compose_pattern_based_review_reply(review_text: object, language: str = "ru") -> str:
    if language != "ru":
        return "Thank you for your review. We are glad you noticed the details of our work and will be happy to see you again."
    detail_phrase = _review_reply_detail_phrase(review_text)
    normalized = _normalize_text_for_semantic_compare(str(review_text or ""))
    has_negative = any(marker in normalized for marker in ("плохо", "ужас", "не понрав", "ждал", "груб", "ошиб", "проблем"))
    if has_negative:
        if detail_phrase:
            return f"Спасибо, что написали. Нам жаль, что {detail_phrase} оставили такое впечатление. Разберём ситуацию внутри команды."
        return "Спасибо, что написали. Нам жаль, что визит оставил такое впечатление. Разберём ситуацию внутри команды."
    if detail_phrase:
        return f"Спасибо за отзыв. Рады, что вы отметили {detail_phrase}. Будем ждать вас снова."
    return "Спасибо за отзыв. Рады, что визит прошёл хорошо. Будем ждать вас снова."

def _normalize_review_reply_output(reply_text: object, review_text: object, *, malformed_model_output: bool = False, language: str = "ru") -> str:
    cleaned = _strip_model_markup(reply_text)
    cleaned = re.sub(r"^\s*\{?\s*\"reply\"\s*:\s*\"?", "", cleaned).strip()
    cleaned = cleaned.strip("{}").strip()
    cleaned = cleaned.strip('"').strip()
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    has_technical_markup = any(marker in cleaned for marker in ("```", "{\"reply\"", '"reply":', "}") )
    too_generic = not _review_reply_has_source_detail(cleaned, review_text)
    if malformed_model_output or has_technical_markup or not cleaned or too_generic:
        return _compose_pattern_based_review_reply(review_text, language=language)
    return cleaned

def _strip_unchanged_service_suggestions(parsed_result: dict) -> dict:
    """
    Убирает псевдо-оптимизации, которые повторяют исходный текст.
    Это защищает UI от «предложений SEO», равных оригиналу.
    """
    if not isinstance(parsed_result, dict):
        return parsed_result
    services = parsed_result.get("services")
    if not isinstance(services, list):
        return parsed_result

    for service in services:
        if not isinstance(service, dict):
            continue

        original_name = str(service.get("original_name") or service.get("name") or "").strip()
        optimized_name = str(service.get("optimized_name") or service.get("optimizedName") or "").strip()
        if original_name and optimized_name:
            if _normalize_text_for_semantic_compare(original_name) == _normalize_text_for_semantic_compare(optimized_name):
                service["optimized_name"] = ""
                if "optimizedName" in service:
                    service["optimizedName"] = ""

        original_desc = str(
            service.get("original_description")
            or service.get("description")
            or service.get("source_description")
            or ""
        ).strip()
        optimized_desc = str(service.get("seo_description") or service.get("seoDescription") or "").strip()
        if original_desc and optimized_desc:
            if _normalize_text_for_semantic_compare(original_desc) == _normalize_text_for_semantic_compare(optimized_desc):
                service["seo_description"] = ""
                if "seoDescription" in service:
                    service["seoDescription"] = ""

    return parsed_result

def _extract_keywords_from_service_name(service_name: str) -> list[str]:
    import re as _re
    text = str(service_name or "").lower().replace("ё", "е")
    cleaned = _re.sub(r"[^a-zа-я0-9\s-]", " ", text, flags=_re.IGNORECASE)
    parts = [p.strip("- ") for p in cleaned.split() if p.strip("- ")]
    stopwords = {
        "и", "в", "на", "с", "по", "для", "или", "от", "до", "при", "без", "под",
        "the", "and", "for", "with", "from",
        "прием", "повторный", "первичный", "услуга",
    }
    keywords: list[str] = []
    for part in parts:
        if len(part) < 4 or part in stopwords:
            continue
        if part not in keywords:
            keywords.append(part)
        if len(keywords) >= 6:
            break
    return keywords

def _select_relevant_service_keywords(
    candidate_keywords: object,
    service_name: str,
    source_description: str = "",
    preferred_category: str | None = None,
) -> list[str]:
    if not isinstance(candidate_keywords, list):
        return []

    service_terms = set(_extract_keywords_from_service_name(service_name))
    service_terms.update(_extract_keywords_from_service_name(source_description))
    service_terms.update(_extract_keywords_from_service_name(preferred_category or ""))

    if not service_terms:
        return []

    selected: list[str] = []
    for raw_keyword in candidate_keywords:
        keyword = str(raw_keyword or "").strip()
        if not keyword:
            continue
        normalized_keyword = _normalize_text_for_semantic_compare(keyword)
        if not normalized_keyword:
            continue
        if any(term in normalized_keyword or normalized_keyword in term for term in service_terms):
            if keyword not in selected:
                selected.append(keyword)
        if len(selected) >= 6:
            break
    return selected

def _is_beauty_service_context(
    service_name: str,
    source_description: str = "",
    preferred_category: str | None = None,
    keywords: object = None,
) -> bool:
    from core.seo_keywords import is_beauty_keyword

    category_text = str(preferred_category or "").strip().lower()
    if category_text and category_text not in {"другое", "общие услуги", "обшие услуги"}:
        if any(token in category_text for token in ("эпиля", "космет", "маник", "педик", "бров", "ресниц", "волос", "spa", "спа")):
            return True

    joined_text = " ".join(
        part for part in [
            str(service_name or ""),
            str(source_description or ""),
            str(preferred_category or ""),
        ]
        if str(part or "").strip()
    ).lower().replace("ё", "е")

    beauty_markers = (
        "эпиля", "космет", "маник", "педик", "бров", "ресниц", "волос",
        "шугар", "депиля", "лазерн", "пилинг", "чистка лица",
    )
    if any(marker in joined_text for marker in beauty_markers):
        return True

    if isinstance(keywords, list):
        for raw_keyword in keywords:
            keyword = str(raw_keyword or "").strip()
            if keyword and is_beauty_keyword(keyword, category_text):
                return True

    return False

def _is_beauty_business_context(business_profile: str) -> bool:
    normalized = str(business_profile or "").strip().lower().replace("ё", "е")
    if not normalized:
        return False
    normalized_spaced = f" {normalized} "
    if " spa " in normalized_spaced:
        return True
    beauty_markers = (
        "beauty", "салон красоты", "парикмах", "барбер", "маник", "педик",
        "космет", "бров", "ресниц", "спа", "массаж", "эпиля",
    )
    return any(marker in normalized for marker in beauty_markers)

def _is_pet_grooming_service_context(
    service_name: str,
    source_description: str = "",
    preferred_category: str | None = None,
    business_profile: str = "",
) -> bool:
    joined = " ".join(
        str(part or "")
        for part in (service_name, source_description, preferred_category, business_profile)
        if str(part or "").strip()
    ).lower().replace("ё", "е")
    pet_markers = (
        "грум", "зоосалон", "собак", "пес", "пса", "кошка", "кошек", "кошк",
        "кот", "кота", "котов", "питом", "шерст", "когт", "тримминг",
        "линьк", "pet grooming", "grooming_salon",
    )
    return any(marker in joined for marker in pet_markers)

def _compose_pet_grooming_service_seo_draft(
    base_name: str,
    keywords: object,
    source_description: str = "",
) -> str:
    name = str(base_name or "").strip() or "Услуга груминга"
    source = str(source_description or "").strip()
    if source and _normalize_text_for_semantic_compare(source) != _normalize_text_for_semantic_compare(name):
        return source

    keyword_items = []
    if isinstance(keywords, list):
        keyword_items = [str(item).strip() for item in keywords if str(item).strip()]

    normalized = _normalize_text_for_semantic_compare(" ".join([name, " ".join(keyword_items)]))
    if "когт" in normalized:
        return f"Аккуратная стрижка когтей собак и кошек с вниманием к комфорту питомца."
    if "тримминг" in normalized:
        return f"Тримминг для собак с учетом типа шерсти и состояния питомца."
    if "линьк" in normalized or "вычес" in normalized:
        return f"Вычесывание и уход за шерстью питомца, чтобы уменьшить линьку и колтуны."
    if "кош" in normalized or "кот" in normalized:
        return f"Груминг для кошек: бережный уход за шерстью, когтями и комфортом питомца."
    if "собак" in normalized or "пес" in normalized:
        return f"Груминг для собак: уход за шерстью, когтями и аккуратным внешним видом питомца."
    return f"{name}: бережный уход за питомцем с учетом его состояния и типа шерсти."

def _strip_unwanted_service_vertical_hallucinations(
    text: str,
    *,
    original_name: str,
    source_description: str,
    business_profile: str,
) -> str:
    result = str(text or "").strip()
    if not result:
        return result

    source_text = " ".join(
        part
        for part in [
            str(original_name or ""),
            str(source_description or ""),
        ]
        if str(part or "").strip()
    ).lower().replace("ё", "е")
    if _is_beauty_business_context(business_profile) or "бьюти" in source_text or "индустр" in source_text and "красот" in source_text:
        return result

    replacements = (
        (" для бьюти-индустрии", ""),
        (" для бьюти индустрии", ""),
        (" в бьюти-индустрии", ""),
        (" в бьюти индустрии", ""),
        (" для индустрии красоты", ""),
        (" в индустрии красоты", ""),
        (" специалистов бьюти-индустрии", "специалистов"),
        (" специалистов индустрии красоты", "специалистов"),
        (" в салоне красоты", ""),
        (" для салона красоты", ""),
    )
    for source, replacement in replacements:
        result = result.replace(source, replacement)
        result = result.replace(source.capitalize(), replacement.capitalize() if replacement else "")

    result = " ".join(result.split())
    return result.strip(" ,-–—")

def _compose_beauty_service_name(base_name: str, keywords: object) -> str:
    source_name = str(base_name or "").strip()
    if not source_name:
        return ""

    name_text = source_name.replace("ё", "е")
    lower_name = name_text.lower()
    keyword_items = []
    if isinstance(keywords, list):
        keyword_items = [str(item).strip() for item in keywords if str(item).strip()]

    method = ""
    for raw_keyword in keyword_items:
        keyword_lower = raw_keyword.lower()
        if "лазерн" in keyword_lower and "эпиля" in keyword_lower:
            method = "Лазерная эпиляция"
            break
        if "электро" in keyword_lower and "эпиля" in keyword_lower:
            method = "Электроэпиляция"
            break
        if "фото" in keyword_lower and "эпиля" in keyword_lower:
            method = "Фотоэпиляция"
            break

    if not method and "эпиля" in lower_name:
        if "лазер" in lower_name:
            method = "Лазерная эпиляция"
        elif "электро" in lower_name:
            method = "Электроэпиляция"
        elif "фото" in lower_name:
            method = "Фотоэпиляция"
        else:
            method = "Эпиляция"

    zone = source_name
    prefixes_to_trim = (
        "лазерная эпиляция", "электроэпиляция", "фотоэпиляция",
        "эпиляция", "депиляция", "шугаринг",
    )
    for prefix in prefixes_to_trim:
        if lower_name.startswith(prefix):
            zone = source_name[len(prefix):].strip(" ,-–—")
            break

    if zone and method:
        zone_lower = zone.lower()
        if zone_lower.startswith("зона "):
            return f"{method} {zone}"
        return f"{method} {zone}"

    if method:
        return method
    return source_name

def _normalize_service_category_value(raw_category: object, fallback: str | None = None) -> str:
    category = str(raw_category or "").strip()
    fallback_category = str(fallback or "").strip()
    generic_categories = {"other", "другое", "разное", "без категории", "общие услуги", "услуги", "категория"}
    if category and category.lower() not in generic_categories:
        return category
    if fallback_category and fallback_category.lower() not in generic_categories:
        return fallback_category
    return "Общие услуги"

def _compose_service_seo_draft(
    base_name: str,
    source_description: str,
    keywords: object,
    region: str | None = None,
    preferred_category: str | None = None,
) -> str:
    description = str(source_description or "").strip()
    if description and not description.lower().startswith("описание услуги:"):
        return description

    keyword_items: list[str] = []
    if isinstance(keywords, list):
        keyword_items = [str(item).strip() for item in keywords if str(item).strip()]

    region_text = str(region or "").strip()
    is_beauty_context = _is_beauty_service_context(
        base_name,
        source_description=source_description,
        preferred_category=preferred_category,
        keywords=keyword_items,
    )

    if _is_pet_grooming_service_context(
        base_name,
        source_description=source_description,
        preferred_category=preferred_category,
    ):
        return _compose_pet_grooming_service_seo_draft(
            base_name,
            keyword_items,
            source_description=source_description,
        )

    if is_beauty_context:
        natural_name = _compose_beauty_service_name(base_name, keyword_items) or str(base_name or "").strip() or "Услуга"
        return f"{natural_name}."

    if keyword_items:
        lead_keywords = ", ".join(keyword_items[:3])
        if region_text:
            return f"{base_name}. Ключевые запросы для {region_text}: {lead_keywords}."
        return f"{base_name}. Ключевые запросы: {lead_keywords}."

    return ""

def _normalize_low_quality_service_suggestions(
    parsed_result: dict,
    region: str | None = None,
    preferred_category: str | None = None,
    business_profile: str = "",
    business_vertical_key: str = "",
    active_pattern_version_ids: list[str] | None = None,
) -> dict:
    if not isinstance(parsed_result, dict):
        return parsed_result
    services = parsed_result.get("services")
    if not isinstance(services, list):
        return parsed_result

    region_text = str(region or "").strip()
    normalized: list[dict] = []
    beauty_canonical_cache: dict[str, dict] = {}
    pattern_version_ids = [
        str(item or "").strip()
        for item in (active_pattern_version_ids or [])
        if str(item or "").strip()
    ]
    for item in services:
        if not isinstance(item, dict):
            continue
        original_name = str(item.get("original_name") or "").strip()
        optimized_name = str(item.get("optimized_name") or "").strip()
        seo_description = str(item.get("seo_description") or "").strip()
        source_description = str(
            item.get("original_description")
            or item.get("description")
            or item.get("source_description")
            or ""
        ).strip()
        keywords = item.get("keywords")
        price = item.get("price")
        category = item.get("category")
        is_beauty_context = is_beauty_optimization_context(
            vertical_key=business_vertical_key,
            business_profile=business_profile,
            service_name=original_name or optimized_name,
            category=category or preferred_category,
        )
        beauty_cache_key = ""
        if is_beauty_context:
            beauty_cache_key = beauty_canonical_service_key(original_name or optimized_name, source_description)
            cached_beauty = beauty_canonical_cache.get(beauty_cache_key)
            if isinstance(cached_beauty, dict):
                normalized.append(dict(cached_beauty))
                continue

        relevant_keywords = _select_relevant_service_keywords(
            keywords,
            original_name or optimized_name,
            source_description,
            preferred_category=category or preferred_category,
        )

        low_name = (
            not optimized_name
            or _normalize_text_for_semantic_compare(optimized_name) == _normalize_text_for_semantic_compare(original_name)
            or "в вашем районе" in optimized_name.lower()
        )
        fallback_reasons: list[str] = []
        if not seo_description:
            fallback_reasons.append("empty_description")
        if seo_description.lower().startswith("описание услуги:"):
            fallback_reasons.append("technical_description_prefix")
        if (
            seo_description
            and "услуга по исходному формату записи" in seo_description.lower()
        ):
            fallback_reasons.append("legacy_fallback_phrase")
        if seo_description and len(seo_description) < 80 and not is_beauty_context:
            fallback_reasons.append("too_short_non_beauty_description")
        if seo_description and (
            _normalize_text_for_semantic_compare(seo_description) == _normalize_text_for_semantic_compare(optimized_name)
            or _normalize_text_for_semantic_compare(seo_description) == _normalize_text_for_semantic_compare(original_name)
        ):
            fallback_reasons.append("description_repeats_name")
        low_description = bool(fallback_reasons)
        low_keywords = not isinstance(keywords, list) or len([k for k in keywords if str(k).strip()]) == 0

        if low_name:
            if is_beauty_context or _is_beauty_service_context(
                original_name or optimized_name,
                source_description=source_description,
                preferred_category=category or preferred_category,
                keywords=relevant_keywords,
            ):
                optimized_name = _compose_beauty_service_name(
                    original_name or optimized_name,
                    relevant_keywords,
                )
            else:
                optimized_name = ""

        if low_description:
            base_name = original_name or optimized_name or "Услуга"
            seo_description = _compose_service_seo_draft(
                base_name=base_name,
                source_description=source_description,
                keywords=relevant_keywords,
                region=region_text,
                preferred_category=category or preferred_category,
            )
            if seo_description:
                fallback_reasons.append("deterministic_description_fallback")

        optimized_name = _strip_unwanted_service_vertical_hallucinations(
            optimized_name,
            original_name=original_name,
            source_description=source_description,
            business_profile=business_profile,
        )
        seo_description = _strip_unwanted_service_vertical_hallucinations(
            seo_description,
            original_name=original_name,
            source_description=source_description,
            business_profile=business_profile,
        )

        if low_keywords:
            keywords = relevant_keywords or _extract_keywords_from_service_name(original_name or optimized_name)
        else:
            keywords = relevant_keywords

        if is_beauty_context:
            guarded = apply_beauty_service_guardrails(
                original_name=original_name or optimized_name,
                optimized_name=optimized_name,
                seo_description=seo_description,
                source_description=source_description,
            )
            optimized_name = str(guarded.get("optimized_name") or "").strip()
            seo_description = str(guarded.get("seo_description") or "").strip()
            item["beauty_attributes"] = guarded.get("beauty_attributes") or {}
            item["guardrail_reasons"] = guarded.get("guardrail_reasons") or []
            item["fallback_used"] = bool(guarded.get("fallback_used"))
            guarded_reason = str(guarded.get("fallback_reason") or "").strip()
            if guarded_reason:
                fallback_reasons.append(guarded_reason)

        normalized_item = {
            "original_name": original_name or optimized_name,
            "optimized_name": optimized_name,
            "seo_description": seo_description,
            "keywords": keywords,
            "industry_key": business_vertical_key or "local_business",
            "pattern_fit": evaluate_pattern_fit(
                f"{optimized_name} {seo_description}",
                business_vertical_key or "local_business",
                mode="service",
            ),
            "seo_keyword_score": evaluate_service_keyword_score(
                f"{optimized_name} {seo_description}",
                keywords,
                f"{original_name} {source_description}",
            ),
            "price": price if price is not None else "",
            "category": _normalize_service_category_value(category, fallback=preferred_category),
            "fallback_used": bool(item.get("fallback_used")) or bool(fallback_reasons),
            "fallback_reason": ",".join([reason for reason in fallback_reasons if reason]),
            "pattern_version_ids": pattern_version_ids,
        }
        if is_beauty_context:
            normalized_item["beauty_attributes"] = item.get("beauty_attributes") or {}
            normalized_item["guardrail_reasons"] = item.get("guardrail_reasons") or []
            normalized_item["fallback_used"] = bool(item.get("fallback_used"))
            if fallback_reasons:
                normalized_item["fallback_used"] = True
            if beauty_cache_key:
                beauty_canonical_cache[beauty_cache_key] = dict(normalized_item)

        normalized.append(normalized_item)

    parsed_result["services"] = normalized if normalized else services
    return parsed_result

def _ensure_usernews_learning_columns(cursor) -> None:
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS original_generated_text TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS edited_before_approve BOOLEAN DEFAULT FALSE")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_key TEXT")
    cursor.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_version TEXT")

@app.route('/api/services/optimize', methods=['POST', 'OPTIONS'])
@rate_limit_if_available("30 per hour")
def services_optimize():
    """Единая точка: перефразирование услуг из текста или файла."""
    try:
        print(f"🔍 Начало обработки запроса /api/services/optimize")
        # Разрешим preflight запросы
        if request.method == 'OPTIONS':
            return ('', 204)
        # Авторизация (опционально можно смягчить)
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({"error": "Требуется авторизация"}), 401

        token = auth_header.split(' ')[1]
        user_data = verify_session(token)
        if not user_data:
            return jsonify({"error": "Недействительный токен"}), 401

        json_payload = request.get_json(silent=True) if request.is_json else {}
        if not isinstance(json_payload, dict):
            json_payload = {}

        tone = request.form.get('tone') or json_payload.get('tone')
        instructions = request.form.get('instructions') or json_payload.get('instructions')
        region = request.form.get('region') or json_payload.get('region')
        business_name = request.form.get('business_name') or json_payload.get('business_name')
        requested_service_category = (
            request.form.get('service_category')
            or request.form.get('category')
            or json_payload.get('service_category')
            or json_payload.get('category')
        )
        length = request.form.get('description_length') or json_payload.get('description_length') or 150
        request_business_id = _resolve_request_business_id(user_data, json_data=json_payload)
        business_profile = ""
        business_vertical_key = "local_business"
        active_service_patterns: list[dict] = []
        business_vertical_prompt = format_service_optimization_vertical_prompt(
            get_service_optimization_vertical_context(business_vertical_key)
        )
        if request_business_id:
            try:
                profile_db = DatabaseManager()
                profile_cursor = profile_db.conn.cursor()
                profile_cursor.execute(
                    """
                    SELECT name, business_type, industry, categories, city, address
                    FROM businesses
                    WHERE id = %s
                    LIMIT 1
                    """,
                    (request_business_id,),
                )
                profile_row = profile_cursor.fetchone()
                profile_data = _row_to_dict(profile_cursor, profile_row) if profile_row else {}
                business_profile = " | ".join(
                    item
                    for item in [
                        str(profile_data.get("name") or business_name or "").strip(),
                        str(profile_data.get("business_type") or "").strip(),
                        str(profile_data.get("industry") or "").strip(),
                        str(profile_data.get("categories") or "").strip(),
                        str(profile_data.get("city") or "").strip(),
                        str(profile_data.get("address") or "").strip(),
                    ]
                    if item
                )
                if not business_name:
                    business_name = str(profile_data.get("name") or "").strip()
                business_vertical_key = detect_service_optimization_vertical(
                    business_name=profile_data.get("name") or business_name,
                    business_type=profile_data.get("business_type"),
                    industry=profile_data.get("industry"),
                    categories=profile_data.get("categories"),
                )
                business_vertical_prompt = format_service_optimization_vertical_prompt(
                    get_service_optimization_vertical_context(business_vertical_key)
                )
                active_service_patterns = load_active_industry_patterns(profile_db.conn, business_vertical_key, "service")
                active_patterns = format_loaded_active_industry_patterns(active_service_patterns)
                if active_patterns:
                    business_vertical_prompt += f"\n{active_patterns}"
                profile_db.close()
            except Exception:
                business_profile = ""

        seo_keywords_list: list[str] = []
        seo_keywords_top10 = ""
        active_service_pattern_version_ids = [
            str(pattern.get("id") or "").strip()
            for pattern in active_service_patterns
            if str(pattern.get("id") or "").strip()
        ]

        def _build_service_optimization_fallback(
            content_text: str,
            unavailable_reason: str | None = None,
            fallback_keywords: object = None,
        ) -> dict:
            fallback_original_name = ""
            fallback_description = ""
            lines = [line.strip() for line in str(content_text or "").splitlines() if line.strip()]
            if lines:
                fallback_original_name = lines[0]
                fallback_description = " ".join(lines[1:])[:280]
            if not fallback_original_name:
                fallback_original_name = "Услуга"
            fallback_description = _compose_service_seo_draft(
                base_name=fallback_original_name,
                source_description=fallback_description,
                keywords=_select_relevant_service_keywords(
                    fallback_keywords,
                    fallback_original_name,
                    fallback_description,
                    preferred_category=requested_service_category,
                ),
                region=region,
                preferred_category=requested_service_category,
            )
            fallback_keyword_items = _select_relevant_service_keywords(
                fallback_keywords,
                fallback_original_name,
                fallback_description,
                preferred_category=requested_service_category,
            )
            fallback_optimized_name = ""
            if _is_beauty_service_context(
                fallback_original_name,
                source_description=fallback_description,
                preferred_category=requested_service_category,
                keywords=fallback_keyword_items,
            ):
                fallback_optimized_name = _compose_beauty_service_name(
                    fallback_original_name,
                    fallback_keyword_items,
                )

            recommendations = [
                "Проверьте формулировку и при необходимости отредактируйте её вручную перед сохранением.",
                "Fallback не заменяет полноценную SEO-генерацию: проверьте Wordstat-ключи и AI-настройки.",
            ]
            if unavailable_reason:
                recommendations.insert(0, unavailable_reason)

            return {
                "services": [
                    {
                        "original_name": fallback_original_name,
                        "optimized_name": fallback_optimized_name,
                        "seo_description": fallback_description,
                        "keywords": fallback_keyword_items,
                        "price": "",
                        "category": _normalize_service_category_value(requested_service_category),
                    }
                ],
                "general_recommendations": recommendations,
                "fallback_used": True,
            }

        def _analyze_service_text_with_fallback(prompt_text: str, content_text: str) -> str:
            try:
                return analyze_text_with_gigachat(
                    prompt_text,
                    task_type="service_optimization",
                    business_id=request_business_id,
                    user_id=user_data['user_id']
                )
            except Exception as exc:
                exc_text = str(exc or "")
                if "GigaChat ключи не настроены" not in exc_text:
                    raise
                fallback_result = _build_service_optimization_fallback(
                    content_text,
                    unavailable_reason="GigaChat сейчас не настроен, поэтому применён базовый fallback без AI-генерации.",
                    fallback_keywords=seo_keywords_list,
                )
                print("⚠️ GigaChat не настроен, используем fallback для оптимизации услуги", flush=True)
                return json.dumps(fallback_result, ensure_ascii=False)

        # Язык результата: получаем из запроса или из профиля пользователя
        requested_language = request.form.get('language') or json_payload.get('language')
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

        # Источник: файл или текст
        file = request.files.get('file') if 'file' in request.files else None
        if file:
            # Проверяем тип файла (прайс-листы + скриншоты)
            allowed_types = [
                'application/pdf',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                'application/vnd.ms-excel',
                'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                'text/plain',
                'text/csv',
                'image/png',
                'image/jpeg',
                'image/jpg'
            ]
            if file.content_type not in allowed_types:
                return jsonify({"error": "Неподдерживаемый тип файла. Разрешены: PDF, DOC, DOCX, XLS, XLSX, TXT, CSV, PNG, JPG, JPEG"}), 400

            # Определяем тип обработки по типу файла
            if file.content_type.startswith('image/'):
                # Для изображений - анализ скриншота
                import base64
                image_data = file.read()
                image_base64 = base64.b64encode(image_data).decode('utf-8')

                # Используем упрощенный промпт для анализа скриншота прайс-листа
                try:
                    with open('prompts/screenshot-analysis-prompt.txt', 'r', encoding='utf-8') as f:
                        prompt_content = f.read()

                    # Парсим SYSTEM_PROMPT и USER_PROMPT_TEMPLATE
                    system_prompt = ""
                    user_prompt_template = ""

                    lines = prompt_content.split('\n')
                    current_section = None

                    for line in lines:
                        if line.strip().startswith('SYSTEM_PROMPT'):
                            current_section = 'system'
                            continue
                        elif line.strip().startswith('USER_PROMPT_TEMPLATE'):
                            current_section = 'user'
                            continue
                        elif line.strip().startswith('"""') and current_section:
                            if current_section == 'system':
                                system_prompt = line.replace('"""', '').strip()
                            elif current_section == 'user':
                                user_prompt_template = line.replace('"""', '').strip()
                            current_section = None
                            continue
                        elif current_section == 'system':
                            system_prompt += line + '\n'
                        elif current_section == 'user':
                            user_prompt_template += line + '\n'

                    # Формируем финальный промпт
                    formatted_user_prompt = user_prompt_template.format(
                        region=region or 'Санкт-Петербург',
                        business_name=business_name or 'Локальный бизнес',
                        business_profile=business_profile or 'не указан',
                        tone=tone or 'Профессиональный',
                        length=length or 150,
                        instructions=instructions or 'Оптимизируй услуги для Яндекс.Карт'
                    )
                    screenshot_prompt = f"{system_prompt}\n\nПрофиль бизнеса: {business_profile or 'не указан'}\n{business_vertical_prompt}\n\n{formatted_user_prompt}"

                except FileNotFoundError:
                    screenshot_prompt = """Проанализируй скриншот прайс-листа или списка услуг и найди все услуги.
Не подменяй отрасль бизнеса. Не добавляй бьюти-термины, если их нет в исходном тексте или профиле бизнеса.

ВЕРНИ РЕЗУЛЬТАТ СТРОГО В JSON ФОРМАТЕ:
{
  "services": [
    {
      "original_name": "исходное название с скриншота",
      "optimized_name": "SEO-оптимизированное название",
      "seo_description": "детальное описание с ключевыми словами",
      "keywords": ["ключ1", "ключ2", "ключ3"],
      "category": "hair|nails|spa|barber|massage|makeup|brows|lashes|other"
    }
  ]
}"""

                print(f"🔍 Анализ скриншота, размер base64: {len(image_base64)} символов")
                result = analyze_screenshot_with_gigachat(
                    image_base64,
                    screenshot_prompt,
                    task_type="service_optimization",
                    business_id=request_business_id,
                    user_id=user_data['user_id']
                )
                print(f"🔍 Результат анализа скриншота: {type(result)}, keys: {result.keys() if isinstance(result, dict) else 'not dict'}")
            else:
                # Для документов - анализ текста
                content = file.read().decode('utf-8', errors='ignore')
        else:
            content = str(json_payload.get('text') or '').strip()

        # Если файл - изображение, результат уже получен выше
        if file and file.content_type.startswith('image/'):
            # Результат анализа скриншота уже в переменной result
            # Для изображений content не используется, но инициализируем пустой строкой
            content = ""
        else:
            # Для текста и документов - проверяем наличие контента
            if not content:
                return jsonify({"error": "Не передан текст услуг или файл"}), 400

            # Загружаем частотные запросы
            try:
                with open('prompts/frequent-queries.txt', 'r', encoding='utf-8') as f:
                    frequent_queries = f.read()
            except FileNotFoundError:
                frequent_queries = "Частотные запросы не найдены"

            # Проверяем наличие косметологических терминов в услугах
            cosmetic_terms = [
                'косметология', 'косметолог', 'чистка лица', 'пилинг лица',
                'ботокс', 'диспорт', 'контурная пластика', 'филлеры',
                'гиалуроновая кислота', 'биоревитализация', 'мезотерапия',
                'плазмолифтинг', 'rf-лифтинг', 'smas-лифтинг', 'ультразвуковой smas',
                'лазерная эпиляция', 'фотоэпиляция', 'лазерное омоложение',
                'лазерная шлифовка', 'нитевой лифтинг', 'липолитики',
                'микротоки', 'аппаратная косметология', 'дермапен', 'микронидлинг',
                'антивозрастные процедуры', 'лечение акне', 'постакне', 'купероз',
                'уход за кожей', 'омоложение лица', 'маска для лица'
            ]

            lower_content = content.lower()
            lower_frequent = frequent_queries.lower() if frequent_queries else ""
            missing_cosmetic_terms = [
                term for term in cosmetic_terms
                if term in lower_content and term not in lower_frequent
            ]

            if missing_cosmetic_terms:
                print(f"⚠️ Найдены косметологические термины без частоток: {missing_cosmetic_terms}")
                # Пытаемся инициировать обновление Wordstat
                try:
                    from update_wordstat_data import main as update_wordstat_main
                    update_wordstat_main()
                except Exception as e:
                    print(f"⚠️ Не удалось запустить обновление Wordstat: {e}")
                # Отправляем уведомление
                try:
                    send_email(
                        "demyanovap@yandex.ru",
                        "Нужны новые Wordstat-ключи (косметология)",
                        "При анализе услуг найдены термины без частотных запросов:\n"
                        + "\n".join(missing_cosmetic_terms)
                    )
                except Exception as e:
                    print(f"⚠️ Не удалось отправить уведомление: {e}")

            try:
                from core.seo_keywords import collect_ranked_keywords

                db_kw = DatabaseManager()
                cur_kw = db_kw.conn.cursor()
                ranked = collect_ranked_keywords(
                    cur_kw,
                    business_id=request_business_id,
                    user_id=user_data['user_id'],
                    service_name=content[:300],
                    service_description=content[:1000],
                    limit=10,
                )
                db_kw.close()
                seo_keywords_list = [
                    str((item or {}).get("keyword", "")).strip()
                    for item in (ranked or {}).get("items", [])
                    if str((item or {}).get("keyword", "")).strip()
                ]
                seo_keywords_top10 = ", ".join(seo_keywords_list[:10])
            except Exception as keywords_error:
                print(f"⚠️ services_optimize: не удалось загрузить SEO-ключи: {keywords_error}", flush=True)

            beauty_attribute_map = ""
            if is_beauty_optimization_context(
                vertical_key=business_vertical_key,
                business_profile=business_profile,
                service_name=content,
                category=requested_service_category,
            ):
                beauty_attribute_map = format_beauty_generation_context(content)

            # Загружаем новый промпт из файла
            try:
                with open('prompts/services-optimization-prompt.txt', 'r', encoding='utf-8') as f:
                    prompt_file = f.read()

                # Парсим SYSTEM_PROMPT и USER_PROMPT_TEMPLATE
                system_prompt = ""
                user_template = ""

                if "SYSTEM_PROMPT = " in prompt_file:
                    system_start = prompt_file.find('SYSTEM_PROMPT = """') + len('SYSTEM_PROMPT = """')
                    system_end = prompt_file.find('"""', system_start)
                    system_prompt = prompt_file[system_start:system_end]

                if "USER_PROMPT_TEMPLATE = " in prompt_file:
                    user_start = prompt_file.find('USER_PROMPT_TEMPLATE = """') + len('USER_PROMPT_TEMPLATE = """')
                    user_end = prompt_file.find('"""', user_start)
                    user_template = prompt_file[user_start:user_end]

                # Загружаем примеры хороших формулировок из БД пользователя
                try:
                    db = DatabaseManager()
                    cur = db.conn.cursor()
                    from core.db_helpers import ensure_user_examples_table
                    ensure_user_examples_table(cur)
                    cur.execute(
                        "SELECT example_text FROM userexamples WHERE user_id = %s AND example_type = 'service' ORDER BY created_at DESC LIMIT 5",
                        (user_data['user_id'],),
                    )
                    rows = cur.fetchall()
                    db.close()
                    examples_list = [row[0] if isinstance(row, tuple) else row['example_text'] for row in rows]
                    good_examples = "\n".join(examples_list) if examples_list else ""
                except Exception:
                    good_examples = ""

                # Формируем финальный промпт
                user_prompt = user_template.replace('{region}', str(region or 'не указан'))
                user_prompt = user_prompt.replace('{business_name}', str(business_name or 'локальный бизнес'))
                user_prompt = user_prompt.replace('{business_profile}', str(business_profile or 'не указан'))
                user_prompt = user_prompt.replace('{business_vertical}', str(business_vertical_prompt))
                user_prompt = user_prompt.replace('{tone}', str(tone or 'профессиональный'))
                user_prompt = user_prompt.replace('{language_name}', language_name)
                user_prompt = user_prompt.replace('{length}', str(length or 150))
                user_prompt = user_prompt.replace('{instructions}', str(instructions or '-'))
                user_prompt = user_prompt.replace('{frequent_queries}', str(frequent_queries))
                user_prompt = user_prompt.replace('{seo_keywords}', str(seo_keywords_top10))
                user_prompt = user_prompt.replace('{seo_keywords_top10}', str(seo_keywords_top10))
                user_prompt = user_prompt.replace('{good_examples}', str(good_examples))
                user_prompt = user_prompt.replace('{beauty_attribute_map}', str(beauty_attribute_map or '-'))
                user_prompt = user_prompt.replace('{content}', str(content[:4000]))

                # Объединяем system и user промпты
                prompt = f"{system_prompt}\n\n{user_prompt}"

            except FileNotFoundError:
                # Fallback на старый промпт
                default_prompt_template = """Ты - SEO-специалист для локального бизнеса. Перефразируй ТОЛЬКО названия услуг и короткие описания для карточек Яндекс.Карт.
Запрещено любые мнения, диалог, оценочные суждения, обсуждение конкурентов, оскорбления. Никакого текста кроме результата.
Не подменяй отрасль бизнеса. Не добавляй "салон", "бьюти", "индустрия красоты", если это не указано в исходной услуге, профиле бизнеса или инструкциях.

Регион: {region}
Название бизнеса: {business_name}
Профиль бизнеса: {business_profile}
Вертикальные правила:
{business_vertical}
Тон: {tone}
Язык результата: {language_name} (все текстовые поля optimized_name, seo_description и general_recommendations должны быть на этом языке)
Длина описания: {length} символов
Дополнительные инструкции: {instructions}

ИСПОЛЬЗУЙ ЧАСТОТНЫЕ ЗАПРОСЫ:
{frequent_queries}

Формат ответа СТРОГО В JSON:
{{
  "services": [
    {{
      "original_name": "...",
      "optimized_name": "...",
      "seo_description": "...",
      "keywords": ["...", "...", "..."],
      "price": null,
      "category": "hair|nails|spa|barber|massage|other"
    }}
  ],
  "general_recommendations": ["...", "..."]
}}

Исходные услуги/контент:
{content}"""

                # Пытаемся получить промпт из БД, если не получилось - используем дефолтный
                prompt_template = get_prompt_from_db('service_optimization', default_prompt_template)

                prompt = (
                    prompt_template
                    .replace('{region}', str(region or 'не указан'))
                    .replace('{business_name}', str(business_name or 'локальный бизнес'))
                    .replace('{business_profile}', str(business_profile or 'не указан'))
                    .replace('{business_vertical}', str(business_vertical_prompt))
                    .replace('{tone}', str(tone or 'профессиональный'))
                    .replace('{language_name}', language_name)
                    .replace('{length}', str(length or 150))
                    .replace('{instructions}', str(instructions or '-'))
                    .replace('{frequent_queries}', str(frequent_queries))
                    .replace('{seo_keywords}', str(seo_keywords_top10))
                    .replace('{seo_keywords_top10}', str(seo_keywords_top10))
                    .replace('{good_examples}', str(good_examples))
                    .replace('{beauty_attribute_map}', str(beauty_attribute_map or '-'))
                    .replace('{content}', str(content[:4000]))
                )

            if requested_service_category:
                prompt += (
                    f"\n\nКРИТИЧНО: Категория услуги: {requested_service_category}."
                    "\nВерни релевантную категорию в поле category и учитывай её при формулировках."
                    "\nНе используй other/другое, если категория задана."
                )

            result = _analyze_service_text_with_fallback(prompt, content)

        # ВАЖНО: analyze_text_with_gigachat всегда возвращает строку
        print(f"🔍 DEBUG services_optimize: result type = {type(result)}")
        print(f"🔍 DEBUG services_optimize: result = {result[:200] if isinstance(result, str) else result}")

        # Парсим JSON из ответа GigaChat
        parsed_result = None
        if isinstance(result, dict):
            # Если словарь (на всякий случай), проверяем наличие ошибки
            if 'error' in result:
                error_msg = result.get('error', 'Ошибка оптимизации')
                print(f"❌ Ошибка в результате: {error_msg}")
                return jsonify({
                    "success": False,
                    "error": error_msg,
                    "raw": result.get('raw_response')
                    }), 502
            parsed_result = result
        elif isinstance(result, str):
            # Если строка, пробуем распарсить как JSON
            try:
                # Ищем JSON объект в строке
                start_idx = result.find('{')
                end_idx = result.rfind('}') + 1
                if start_idx != -1 and end_idx != 0:
                    json_str = result[start_idx:end_idx]
                    parsed_result = json.loads(json_str)
                    if isinstance(parsed_result, dict) and 'error' in parsed_result:
                        error_msg = parsed_result.get('error', 'Ошибка оптимизации')
                        print(f"❌ Ошибка в результате: {error_msg}")
                        return jsonify({
                            "success": False,
                            "error": error_msg,
                            "raw": result
                        }), 502
                else:
                    # JSON не найден, пробуем распарсить всю строку
                    parsed_result = json.loads(result)
            except json.JSONDecodeError:
                print(f"❌ Не удалось распарсить JSON из результата")
                print(f"❌ Полный результат: {result[:500]}")
                return jsonify({
                    "success": False,
                    "error": "Не удалось распарсить результат оптимизации",
                    "raw": result
                }), 502
        else:
            print(f"❌ Неожиданный тип результата: {type(result)}")
            return jsonify({
                "success": False,
                "error": "Неожиданный формат результата",
                "raw": str(result)
            }), 502

        # Проверяем, что parsed_result - это словарь
        if not isinstance(parsed_result, dict):
            print(f"❌ Ошибка: parsed_result не является словарём, тип: {type(parsed_result)}")
            parsed_result = {}
        else:
            parsed_result = _strip_unchanged_service_suggestions(parsed_result)

        optimized_services = parsed_result.get("services") if isinstance(parsed_result, dict) else None
        if not isinstance(optimized_services, list) or len(optimized_services) == 0:
            # Retry once with stricter prompt if model returned empty payload (e.g. "{}")
            retry_prompt = (
                prompt
                + "\n\nВАЖНО: Верни СТРОГО JSON-объект без пояснений."
                + "\nВнутри обязательно поле services (массив минимум из 1 элемента)."
                + "\nКаждый элемент должен содержать: original_name, optimized_name, seo_description, keywords, price, category."
            )
            retry_raw = _analyze_service_text_with_fallback(retry_prompt, content)
            try:
                if isinstance(retry_raw, str):
                    retry_start = retry_raw.find('{')
                    retry_end = retry_raw.rfind('}') + 1
                    retry_json = retry_raw[retry_start:retry_end] if retry_start != -1 and retry_end > retry_start else retry_raw
                    retry_parsed = json.loads(retry_json)
                elif isinstance(retry_raw, dict):
                    retry_parsed = retry_raw
                else:
                    retry_parsed = {}
            except Exception:
                retry_parsed = {}

            if isinstance(retry_parsed, dict):
                retry_parsed = _strip_unchanged_service_suggestions(retry_parsed)
                retry_services = retry_parsed.get("services")
                if isinstance(retry_services, list) and len(retry_services) > 0:
                    parsed_result = retry_parsed
                    optimized_services = retry_services

        if not isinstance(optimized_services, list) or len(optimized_services) == 0:
            # Last-resort deterministic fallback: do not fail request for operator UI
            parsed_result = _build_service_optimization_fallback(content, fallback_keywords=seo_keywords_list)
        else:
            parsed_result = _normalize_low_quality_service_suggestions(
                parsed_result,
                region=region,
                preferred_category=requested_service_category,
                business_profile=business_profile,
                business_vertical_key=business_vertical_key,
                active_pattern_version_ids=active_service_pattern_version_ids,
            )

        # Apply quality normalization for fallback branch as well
        parsed_result = _normalize_low_quality_service_suggestions(
            parsed_result,
            region=region,
            preferred_category=requested_service_category,
            business_profile=business_profile,
            business_vertical_key=business_vertical_key,
            active_pattern_version_ids=active_service_pattern_version_ids,
        )

        # Сохраним в БД (как оптимизацию прайса, даже для текстового режима)
        db = DatabaseManager()
        cursor = db.conn.cursor()
        # Гарантируем наличие таблицы PricelistOptimizations
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS PricelistOptimizations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                original_file_path TEXT,
                optimized_data TEXT,
                services_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            )
            """
        )
        optimization_id = str(uuid.uuid4())
        upload_dir = 'uploads/pricelists'
        os.makedirs(upload_dir, exist_ok=True)
        # Сохраним сырой текст в файл для истории
        raw_path = os.path.join(upload_dir, f"{optimization_id}_raw.txt")
        with open(raw_path, 'w', encoding='utf-8') as f:
            f.write(content)

        result = parsed_result
        services_count = len(result.get('services', [])) if isinstance(result.get('services'), list) else 0
        if active_service_patterns:
            record_industry_pattern_impact_event(
                db.conn,
                active_service_patterns,
                industry_key=business_vertical_key,
                pattern_type="service",
                business_id=request_business_id or "",
                user_id=user_data['user_id'],
                source="services_optimize",
                event_type="applied",
                result_status="used_in_prompt",
                metrics={"services_count": services_count},
            )
            impact_metrics = build_pattern_impact_metrics(result, "service")
            record_industry_pattern_impact_event(
                db.conn,
                active_service_patterns,
                industry_key=business_vertical_key,
                pattern_type="service",
                business_id=request_business_id or "",
                user_id=user_data['user_id'],
                source="services_optimize",
                event_type="result",
                result_status="needs_review" if int(impact_metrics.get("needs_review") or 0) > 0 else "good",
                metrics=impact_metrics,
            )
        cursor.execute("""
            INSERT INTO PricelistOptimizations (id, user_id, original_file_path, optimized_data, services_count, expires_at)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            optimization_id,
            user_data['user_id'],
            raw_path,
            json.dumps(result, ensure_ascii=False),
            services_count,
            (datetime.now() + timedelta(days=1)).isoformat()
        ))
        db.conn.commit()
        db.close()

        first_service = None
        if isinstance(result.get("services"), list) and result.get("services"):
            first_service = result.get("services")[0]
        draft_name = ""
        if isinstance(first_service, dict):
            draft_name = str(first_service.get("optimized_name") or first_service.get("original_name") or "")
        record_ai_learning_event(
            capability="services.optimize",
            event_type="generated",
            intent="operations",
            user_id=user_data['user_id'],
            business_id=request_business_id,
            prompt_key="service_optimization",
            prompt_version="v1",
            draft_text=draft_name or None,
            metadata={"optimization_id": optimization_id, "services_count": services_count},
        )

        return jsonify({
            "success": True,
            "optimization_id": optimization_id,
            "result": result,
            "meta": {"tone": tone or 'professional', "region": region, "length": int(length) if str(length).isdigit() else 150}
        })

    except Exception as e:
        print(f"❌ Ошибка оптимизации услуг: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route('/api/examples', methods=['GET', 'POST', 'OPTIONS'])
def user_service_examples():
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
        from core.db_helpers import ensure_user_examples_table
        ensure_user_examples_table(cur)

        if request.method == 'GET':
            cur.execute(
                "SELECT id, example_text, created_at FROM userexamples WHERE user_id = %s AND example_type = 'service' ORDER BY created_at DESC",
                (user_data['user_id'],),
            )
            rows = cur.fetchall()
            db.close()
            examples = []
            for row in rows:
                rd = _row_to_dict(cur, row) if row else {}
                examples.append({"id": rd.get("id"), "text": rd.get("example_text"), "created_at": rd.get("created_at")})
            return jsonify({"success": True, "examples": examples})

        # POST
        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()
        if not text:
            db.close()
            return jsonify({"error": "Текст примера обязателен"}), 400
        # Ограничим 5 примеров на пользователя
        cur.execute("SELECT COUNT(*) AS cnt FROM userexamples WHERE user_id = %s AND example_type = 'service'", (user_data['user_id'],))
        count_row = cur.fetchone()
        count_data = _row_to_dict(cur, count_row) if count_row else {}
        count = count_data.get("cnt", 0) or 0
        if count >= 5:
            db.close()
            return jsonify({"error": "Максимум 5 примеров"}), 400
        example_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO userexamples (id, user_id, example_type, example_text) VALUES (%s, %s, 'service', %s)",
            (example_id, user_data['user_id'], text),
        )
        db.conn.commit()
        db.close()
        return jsonify({"success": True, "id": example_id})
    except Exception as e:
        print(f"❌ Ошибка работы с примерами услуг: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/examples/<example_id>', methods=['DELETE', 'OPTIONS'])
def delete_user_service_example(example_id: str):
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
            "DELETE FROM userexamples WHERE id = %s AND user_id = %s AND example_type = 'service'",
            (example_id, user_data['user_id']),
        )
        deleted = cur.rowcount
        db.conn.commit()
        db.close()
        if deleted == 0:
            return jsonify({"error": "Пример не найден"}), 404
        return jsonify({"success": True})
    except Exception as e:
        print(f"❌ Ошибка удаления примера: {e}")
        return jsonify({"error": str(e)}), 500

def _normalize_news_site_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    return f"https://{text}"

def _clean_news_site_description(value: Any) -> str:
    text = html.unescape(str(value or "").strip())
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip(" \t\r\n|—-")[:500]

def _extract_news_site_description(html_text: str) -> str:
    if not html_text:
        return ""
    meta_patterns = [
        r'<meta[^>]+name=["\\\']description["\\\'][^>]+content=["\\\']([^"\\\']+)["\\\']',
        r'<meta[^>]+property=["\\\']og:description["\\\'][^>]+content=["\\\']([^"\\\']+)["\\\']',
        r'<meta[^>]+name=["\\\']twitter:description["\\\'][^>]+content=["\\\']([^"\\\']+)["\\\']',
        r'<meta[^>]+content=["\\\']([^"\\\']+)["\\\'][^>]+name=["\\\']description["\\\']',
        r'<meta[^>]+content=["\\\']([^"\\\']+)["\\\'][^>]+property=["\\\']og:description["\\\']',
    ]
    for pattern in meta_patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match:
            description = _clean_news_site_description(match.group(1))
            if description:
                return description
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html_text, flags=re.IGNORECASE | re.DOTALL)
    return _clean_news_site_description(title_match.group(1) if title_match else "")

def _fetch_news_site_description(site_url: Any) -> str:
    url = _normalize_news_site_url(site_url)
    if not url:
        return ""
    try:
        response = requests.get(
            url,
            headers={"User-Agent": "LocalOSBot/1.0 (+https://localos.pro)"},
            timeout=5,
        )
        if response.status_code >= 400:
            return ""
        return _extract_news_site_description(response.text or "")
    except Exception:
        return ""

def _news_context_is_cultural_space(context: str) -> bool:
    lower = str(context or "").lower()
    cultural_markers = ["культур", "афиша", "лекци", "концерт", "стендап", "мастер-класс", "событи"]
    return any(marker in lower for marker in cultural_markers)

def _news_text_has_school_hallucination(text: str) -> bool:
    lower = str(text or "").lower()
    school_markers = ["школ", "учебн", "обучен", "детей и подростков", "ребенка", "ребёнка"]
    return any(marker in lower for marker in school_markers)

def _news_service_scope_terms(service_context: Any) -> list[str]:
    normalized = _normalize_text_for_semantic_compare(str(service_context or ""))
    stop_words = {
        "услуга", "описание", "питомца", "питомцев", "животных", "домашних",
        "безопасная", "аккуратная", "бережная", "проверкой", "проверка",
    }
    return [
        term
        for term in normalized.split()
        if len(term) >= 4 and term not in stop_words
    ][:10]

def _news_text_has_service_anchor(generated_text: Any, service_context: Any) -> bool:
    terms = _news_service_scope_terms(service_context)
    if not terms:
        return True
    normalized = _normalize_text_for_semantic_compare(str(generated_text or ""))
    return any(term in normalized for term in terms)

def _news_text_has_demo_platform_drift(generated_text: Any) -> bool:
    normalized = _normalize_text_for_semantic_compare(str(generated_text or ""))
    drift_markers = [
        "localos",
        "ai инструмент",
        "платформ",
        "автоматизац",
        "материнск",
        "обзорн визит",
        "центр обслуживан партнер",
        "партнерск программ",
        "получить новых клиент",
        "ведение зоо салон",
        "делимся опытом",
    ]
    return any(marker in normalized for marker in drift_markers)

def _service_focused_news_fallback(
    *,
    business_name: str,
    service_context: Any,
    language_code: str,
) -> str:
    service_text = str(service_context or "").strip()
    service_name = service_text
    if service_text.lower().startswith("услуга:"):
        service_name = service_text.split(".", 1)[0].replace("Услуга:", "").strip()
    service_name = service_name or "услуга"

    normalized = _normalize_text_for_semantic_compare(service_name)
    if language_code == "ru":
        if "уш" in normalized:
            return (
                f"Новость компании: в {business_name} доступна услуга «{service_name}». "
                "Это аккуратный уход за ушами питомца с вниманием к комфорту и состоянию животного. "
                "Запись и подробности — по телефону или в сообщениях."
            )
        return (
            f"Новость компании: в {business_name} доступна услуга «{service_name}». "
            "Администратор подскажет детали услуги и поможет выбрать удобное время визита. "
            "Запись и подробности — по телефону или в сообщениях."
        )

    if "ear" in normalized or "уш" in normalized:
        return (
            f"Business update: {business_name} offers {service_name}. "
            "This is gentle ear care for pets with attention to comfort and condition. "
            "For details or booking, contact us by phone or message."
        )
    return (
        f"Business update: {business_name} offers {service_name}. "
        "Contact us by phone or message to check details and choose a convenient visit time."
    )

def _clean_generated_news_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = re.sub(r"^\s*```(?:json|JSON)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    text = text.replace("\\n", "\n").replace("\\\"", "\"")

    payload_candidates = [text]
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace >= 0 and last_brace > first_brace:
        payload_candidates.append(text[first_brace:last_brace + 1])

    for candidate in payload_candidates:
        try:
            parsed = json.loads(candidate)
        except Exception:
            continue
        if isinstance(parsed, dict):
            for key in ("news", "text", "content", "draft"):
                parsed_value = str(parsed.get(key) or "").strip()
                if parsed_value:
                    text = parsed_value
                    break
        elif isinstance(parsed, str):
            text = parsed.strip()
        if text:
            break

    news_match = re.search(r'"(?:news|text|content|draft)"\s*:\s*"', text, flags=re.IGNORECASE | re.DOTALL)
    if news_match:
        text = text[news_match.end():].strip()
        text = re.sub(r"\s*}\s*$", "", text).strip()
        text = re.sub(r'\s*,\s*"[^"]+"\s*:\s*.*$', "", text, flags=re.DOTALL).strip()

    text = re.sub(r"^\s*\{?\s*\"(?:news|text|content|draft)\"\s*:\s*\"?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\s*}\s*$", "", text).strip()
    text = re.sub(r"\s+", " ", text).strip()
    if text.count('"') % 2 == 1:
        last_quote_index = text.rfind('"')
        if last_quote_index >= 0:
            text = (text[:last_quote_index] + text[last_quote_index + 1:]).strip()

    for _ in range(3):
        stripped = text.strip()
        if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'", "«", "“"}:
            text = stripped[1:-1].strip()
            continue
        if stripped.endswith('"') and stripped.count('"') % 2 == 1:
            text = stripped[:-1].strip()
            continue
        break
    return text
