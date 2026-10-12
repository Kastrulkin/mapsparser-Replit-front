"""Scoped production function replacements; loaded only by the guarded installer.
Not a second content runtime. See README.md in this directory.
"""
from typing import Any
import re

def _load_content_plan_service_sources(cursor: Any, business_id: str, limit: int = 10) -> list[dict[str, Any]]:
    try:
        cursor.execute(
            """
            SELECT name, description, category, id, source, updated_at
            FROM userservices
            WHERE business_id = %s
              AND (is_active IS TRUE OR is_active IS NULL)
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (business_id, limit),
        )
        rows = cursor.fetchall() or []
    except Exception:
        return []
    sources: list[dict[str, Any]] = []
    for row in rows:
        name = _normalize_fact_text(_row_get(row, "name", 0, ""))
        category = _normalize_fact_text(_row_get(row, "category", 2, ""))
        description = _normalize_fact_text(_row_get(row, "description", 1, ""))
        if not name:
            continue
        detail_parts = [part for part in [category, description[:180]] if part]
        detail = f" ({'; '.join(detail_parts)})" if detail_parts else ""
        sources.append({
            "id": f"service:{_row_get(row, 'id', 3, '')}",
            "type": "business_service", "label": name, "fact": f"{name}{detail}",
            "business_id": business_id, "table": "userservices",
            "record_id": str(_row_get(row, "id", 3, "")),
            "origin": str(_row_get(row, "source", 4, "") or ""),
            "observed_at": str(_row_get(row, "updated_at", 5, "") or ""),
        })
    return sources

def _load_content_plan_service_facts(cursor: Any, business_id: str, limit: int = 10) -> str:
    return "\n".join(f"- {source['fact']}" for source in _load_content_plan_service_sources(cursor, business_id, limit))

def _with_content_fact_sources(brief: dict[str, Any], facts: dict[str, Any], business_id: str = "") -> dict[str, Any]:
    """One immutable-by-convention source snapshot for both writer and validator."""
    sources = [dict(source) for source in brief.get("sources") or [] if isinstance(source, dict)]
    for field, label in (
        ("name", "Название"), ("city", "Город"), ("address", "Адрес"),
        ("business_type", "Тип бизнеса"), ("industry", "Отрасль"),
        ("categories", "Категории"), ("description", "Описание бизнеса"), ("site", "Сайт"),
    ):
        value = str(facts.get(field) or "").strip()
        if value:
            sources.append({"id": f"business_profile:{field}", "type": "business",
                            "label": label, "fact": value, "business_id": business_id,
                            "table": "businesses", "record_id": business_id, "field": field})
    site_text = str(facts.get("site_description") or "").strip()
    if site_text:
        provenance = facts.get("website_source") or {}
        sources.append({"id": "business_website", "type": "website", "label": "Содержание сайта",
                        "fact": site_text, "business_id": business_id,
                        "url": provenance.get("final_url") or provenance.get("url") or facts.get("site"),
                        "observed_at": provenance.get("fetched_at") or "", "untrusted": True})
    service_sources = facts.get("service_sources")
    if isinstance(service_sources, list):
        sources.extend(dict(source) for source in service_sources if isinstance(source, dict)
                       and (not source.get("business_id") or str(source.get("business_id")) == business_id))
    elif str(facts.get("services") or "").strip():
        sources.append({"id": "business_services", "type": "business_service",
                        "label": "Сохранённые услуги", "fact": str(facts["services"]),
                        "business_id": business_id, "table": "userservices"})
    unique = {str(source.get("id")): source for source in sources if source.get("id") and source.get("fact")}
    return {**brief, "fact_sources": list(unique.values()), "fact_sources_schema": "content_fact_sources_v1"}

def _content_brief_fact_sources(brief: dict[str, Any]) -> list[dict[str, Any]]:
    sources = brief.get("fact_sources") if "fact_sources" in brief else brief.get("sources")
    return [source for source in sources or [] if isinstance(source, dict)]

def _build_content_brief_v1(
    item: dict[str, Any],
    facts: dict[str, Any],
    evidence_sources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    metadata = _item_metadata(item)
    answers = metadata.get("brief_answers") if isinstance(metadata.get("brief_answers"), dict) else {}
    theme = _clean_brief_answer(item.get("theme"), 500)
    goal = _clean_brief_answer(item.get("goal"), 700)
    source_kind = _clean_brief_answer(item.get("source_kind"), 80).lower()
    source_ref = _clean_brief_answer(item.get("source_ref"), 800)
    seo_keyword = _clean_brief_answer(item.get("seo_keyword"), 300)
    content_type = _clean_brief_answer(item.get("content_type"), 80).lower()
    owner_event = _clean_brief_answer(answers.get("infopovod") or answers.get("event") or "", 12000)
    event = owner_event
    if not event and source_kind not in {"seo_keyword", "audit_signal", "search", "seasonal"}:
        event = source_ref or theme
    detail_answer = _clean_brief_answer(answers.get("confirmed_details") or answers.get("details") or "", 4000)
    story_facts = _clean_brief_answer(answers.get("story_facts"), 12000)
    story_objective = _story_fact_objective(item)
    evidence = [dict(source) for source in evidence_sources or [] if isinstance(source, dict)]
    owner_story_confirmed = bool(
        story_objective
        and len(owner_event) >= 120
        and CONTENT_STORY_SIGNAL_RE.search(owner_event)
    )
    if owner_story_confirmed:
        evidence = [source for source in evidence if str(source.get("type") or "") != "public_review"]
    relevant_services = _relevant_service_names_for_item(facts.get("services"), item, limit=3)
    details: list[str] = []
    if detail_answer:
        details.append(detail_answer)
    if story_facts:
        details.append(story_facts)
    if owner_story_confirmed:
        details.append(owner_event)
    details.extend(_clean_brief_answer(source.get("fact"), 700) for source in evidence[:3])
    if source_ref and source_ref != event and source_kind not in {"seo_keyword", "audit_signal", "search"}:
        details.append(source_ref)
    if content_type in {"service", "service_intro"} and relevant_services:
        details.extend(relevant_services)
    sources: list[dict[str, Any]] = []
    if event:
        sources.append(
            {
                "id": "event",
                "type": "owner" if owner_event else "plan",
                "label": "Подтверждённая история владельца" if owner_story_confirmed else "Инфоповод",
                "fact": event,
                "story_evidence": owner_story_confirmed,
            }
        )
    if source_ref and source_kind not in {"seo_keyword", "audit_signal", "search"}:
        sources.append({"id": "source_ref", "type": source_kind or "plan", "label": "Источник темы", "fact": source_ref})
    if detail_answer:
        sources.append({"id": "owner_detail", "type": "owner", "label": "Добавлено владельцем", "fact": detail_answer})
    if story_facts:
        sources.append({"id": "story_facts", "type": "owner", "label": "Факты истории", "fact": story_facts})
    editorial_focus = _clean_brief_answer(metadata.get('editorial_focus'),1500)
    if editorial_focus:
        goal = editorial_focus + '. ' + goal
    source_answer = _clean_brief_answer(answers.get("source"), 500)
    if source_answer:
        sources.append({"id": "owner_source", "type": "owner", "label": "Источник владельца", "fact": source_answer})
    if relevant_services and content_type in {"service", "service_intro"}:
        sources.append({"id": "services", "type": "business", "label": "Услуги бизнеса", "fact": ", ".join(relevant_services)})
    sources.extend(evidence)
    site_fact = _clean_brief_answer(facts.get("site_description") or facts.get("description"), 500)
    if site_fact:
        sources.append({"id": "business_description", "type": "business", "label": "Сайт или карточка", "fact": site_fact})
    story_evidence = [
        source
        for source in sources
        if bool(source.get("story_evidence")) or str(source.get("id") or "") == "story_facts"
    ]
    is_event = _normalize_publication_objective(item) in {"announcement", "agenda", "reminder", "photo_report"} or content_type == "event"
    date_blob = " ".join([event, detail_answer, source_ref, theme])
    has_date = bool(CONTENT_BRIEF_DATE_RE.search(date_blob)) or bool(_clean_brief_answer(answers.get("date_status"), 120))
    is_search_only = source_kind in {"seo_keyword", "audit_signal", "search"} and not _clean_brief_answer(answers.get("infopovod"))
    missing: list[str] = []
    if story_objective and not story_evidence:
        missing.append("story_facts")
    if not event or is_search_only:
        missing.append("infopovod")
    if not details:
        missing.append("confirmed_details")
    if is_event and not has_date:
        missing.append("date_status")
    if not sources or (len(sources) == 1 and sources[0].get("id") == "business_description"):
        missing.append("source")
    questions_by_key = {
        "infopovod": "Что произошло или о чём именно хотите рассказать?",
        "confirmed_details": "Добавьте одну конкретную деталь: дату, участника, формат или пользу.",
        "date_status": "Когда это состоится? Если дата ещё не объявлена, так и напишите.",
        "source": "Откуда взята эта информация: афиша, сайт, услуга или ваш комментарий?",
        "story_facts": STORY_FACTS_QUESTION,
    }
    unique_missing = list(dict.fromkeys(missing))[:3]
    return _with_content_fact_sources({
        "schema": "content_brief_v1",
        "event": event,
        "confirmed_details": details[:5],
        "audience": _clean_brief_answer(answers.get("audience") or "Клиенты бизнеса", 300),
        "main_idea": _clean_brief_answer(answers.get("main_idea") or theme, 500),
        "expected_action": _clean_brief_answer(answers.get("expected_action") or goal or "Открыть карточку и узнать подробности", 500),
        "target_platforms": answers.get("target_platforms") if isinstance(answers.get("target_platforms"), list) else [],
        "sources": sources[:8],
        "seo_signal": seo_keyword,
        "requires_story_facts": bool(story_objective),
        "story_evidence_source_ids": [str(source.get("id") or "") for source in story_evidence],
        "story_objective": story_objective,
        "complete": not unique_missing,
        "missing_fields": unique_missing,
        "questions": [questions_by_key[key] for key in unique_missing],
    }, facts, str(item.get("business_id") or ""))

def _content_brief_prompt_block(brief: dict[str, Any]) -> str:
    source_lines = [
        f"- {item.get('id')}: {item.get('label')} — {item.get('fact')}"
        for item in _content_brief_fact_sources(brief)
    ]
    return "\n".join(
        [
            f"Инфоповод: {brief.get('event') or 'нет'}",
            f"Подтверждённые детали: {'; '.join(brief.get('confirmed_details') or []) or 'нет'}",
            f"Аудитория: {brief.get('audience') or 'нет'}",
            f"Главная мысль: {brief.get('main_idea') or 'нет'}",
            f"Ожидаемое действие: {brief.get('expected_action') or 'нет'}",
            "Источники фактов:",
            *(source_lines or ["- нет"]),
        ]
    )

def _strip_content_json_markdown(raw: Any) -> str:
    """Remove a transport wrapper, never repair or reinterpret invalid JSON."""
    text = str(raw or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.IGNORECASE | re.DOTALL)
    if fenced:
        text = str(fenced.group(1) or "").strip()
    return text

def _parse_content_candidates(raw: Any) -> list[dict[str, Any]]:
    text = _strip_content_json_markdown(raw)
    candidates: Any = None
    for candidate_text in (text, text[text.find("{"):text.rfind("}") + 1] if "{" in text and "}" in text else ""):
        if not candidate_text:
            continue
        try:
            parsed = json.loads(candidate_text)
        except Exception:
            continue
        candidates = parsed.get("candidates") if isinstance(parsed, dict) else parsed
        if isinstance(candidates, list):
            break
    if not isinstance(candidates, list):
        return []
    result: list[dict[str, Any]] = []
    for index, item in enumerate(candidates[:3]):
        if not isinstance(item, dict):
            continue
        candidate_text = _format_long_generated_paragraphs(
            _sanitize_generated_news_text(str(item.get("text") or ""))
        )
        if not candidate_text:
            continue
        result.append(
            {
                "id": str(item.get("id") or f"variant-{index + 1}"),
                "angle": str(item.get("angle") or f"Подход {index + 1}").strip()[:80],
                "text": candidate_text,
                "used_fact_ids": [str(value) for value in item.get("used_fact_ids") or []],
                "unsupported_facts": [str(value) for value in item.get("unsupported_facts") or []],
            }
        )
    return result

UNSUPPORTED_CLAIM_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("тысячи клиентов", re.compile(r"\bтысяч\w*\b", re.IGNORECASE)),
    ("сотни клиентов", re.compile(r"\bсот(?:н\w*|ен)\b", re.IGNORECASE)),
    ("миллионы клиентов", re.compile(r"\bмиллион\w*\b", re.IGNORECASE)),
    ("младший или старший герой", re.compile(r"\b(?:младш|старш)\w*\b", re.IGNORECASE)),
    ("неподтверждённая оценка героя", re.compile(r"\b(?:капризн|сам\w*\s+капризн)\w*\b", re.IGNORECASE)),
    ("новый этап жизни героя", re.compile(r"\bтеперь\s+(?:он|она)\s+готовится\s+к\s+детск\w+\s+сад\w*", re.IGNORECASE)),
)

def _content_creative_warnings(text: str) -> list[str]:
    """Editorial suggestions, not factual or publication blockers."""
    patterns = (
        r"\bподход\w*\s+(?:даже\s+)?к\s+сам(?:ым|ому)\s+\w+",
        r"\bродител\w*\s+спокойн\w*\s+за\s+результат",
        r"\bсохраня\w*\s+спокойств\w*\s+родител\w*",
        r"\bдети\s+выходят\s+довольн\w*",
    )
    return ["Рекомендуется смягчить обобщение о результате; это не блокирует текст"] if any(
        re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns
    ) else []

def _unsupported_candidate_claims(text: str, brief: dict[str, Any]) -> list[str]:
    source_facts = [
        str(item.get("fact") or "")
        for item in _content_brief_fact_sources(brief)
        if isinstance(item, dict) and str(item.get("fact") or "").strip()
    ]
    factual_text = " ".join(
        [
            *source_facts,
            *(str(value or "") for value in brief.get("confirmed_details") or []),
        ]
    ).lower()
    issues: list[str] = []
    factual_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", factual_text))
    candidate_numbers = set(re.findall(r"\b\d+(?:[.,]\d+)?\b", text))
    if source_facts:
        for value in sorted(candidate_numbers.difference(factual_numbers)):
            issues.append(f"Цифра {value} не подтверждена источниками")
    for label, pattern in UNSUPPORTED_CLAIM_PATTERNS:
        if pattern.search(text) and not pattern.search(factual_text):
            issues.append(f"Утверждение «{label}» не подтверждено источниками")
    has_reviews = any(
        isinstance(source, dict) and source.get("type") == "public_review"
        for source in brief.get("sources") or []
    )
    has_confirmed_story = bool(brief.get("story_evidence_source_ids"))
    if has_reviews and not has_confirmed_story and re.search(
        r"\b(?:мой|моя|моему|моей)\s+(?:сын\w*|доч\w*|реб[её]нок\w*)\b|\bбоялась\b",
        text, flags=re.IGNORECASE,
    ):
        issues.append("Отзыв нельзя выдавать за личную историю автора без подтверждённых фактов истории")
    return issues

def _score_content_candidate(candidate: dict[str, Any], brief: dict[str, Any], voice: dict[str, Any]) -> dict[str, Any]:
    text = str(candidate.get("text") or "").strip()
    allowed_ids = {str(item.get("id") or "") for item in _content_brief_fact_sources(brief)}
    used_ids = {str(value) for value in candidate.get("used_fact_ids") or []}
    unsupported = [value for value in candidate.get("unsupported_facts") or [] if str(value).strip()]
    unsupported.extend(_unsupported_candidate_claims(text, brief))
    grounded = bool(used_ids) and used_ids.issubset(allowed_ids) and not unsupported
    forbidden = [str(value).lower() for value in voice.get("forbidden_phrases") or [] if str(value).strip()]
    default_cliches = ["уютное пространство", "профессиональная команда", "идеальный выбор", "ждём вас"]
    cliche_hits = [value for value in [*forbidden, *default_cliches] if value in text.lower()]
    cliche_hits.extend(label for label, pattern in SLOP_PATTERNS if pattern.search(text))
    paragraph_count = len([value for value in text.split("\n\n") if value.strip()])
    style_issues: list[str] = []
    if len(text) > 260 and paragraph_count < 2:
        style_issues.append("Разделите длинный текст на короткие абзацы")
    if paragraph_count > 5:
        style_issues.append("Слишком много абзацев для короткой публикации")
    if re.search(r"#[\wа-яё-]+", text, flags=re.IGNORECASE):
        style_issues.append("Хэштеги не нужны")
    if text.count("!") > 1:
        style_issues.append("Слишком много восклицаний")
    meta_copy_markers = (
        "цель публикации",
        "бизнес-задача",
        "в фокусе публикации",
        "эта публикация",
        "публикация должна",
        "контент-план",
    )
    if any(marker in text.lower() for marker in meta_copy_markers):
        style_issues.append("В текст попала внутренняя формулировка контент-плана")
    style_issues.extend(f"Рекламное клише: {value}" for value in dict.fromkeys(cliche_hits))
    editorial_issues, voice_issues, clarity_issues, story_issues = _editorial_quality_issues(text, voice)
    natural_review = review_content_text(text, brief=brief)
    natural_issues = [str(value) for value in natural_review.get("quality_issues") or [] if str(value)]
    story_issues.extend(_confirmed_story_coverage_issues(text, brief))
    style_issues.extend(editorial_issues)
    style_issues.extend(voice_issues)
    style_issues.extend(clarity_issues)
    style_issues.extend(story_issues)
    style_issues.extend(natural_issues)
    story_source_ids = {str(value) for value in brief.get("story_evidence_source_ids") or [] if str(value)}
    if brief.get("story_objective") and story_source_ids and not used_ids.intersection(story_source_ids):
        style_issues.append("История не опирается на реальный эпизод из источника")
    score = 0
    if grounded:
        score += 55
    if 140 <= len(text) <= 700:
        score += 10
    if any(char.isdigit() for char in text) or len(brief.get("confirmed_details") or []) >= 1:
        score += 8
    if not cliche_hits:
        score += 10
    if 1 <= paragraph_count <= 5:
        score += 5
    return {
        **candidate,
        "score": min(score, 100),
        "grounded": grounded,
        "factual_gate_passed": grounded,
        "neuroslop_passed": not cliche_hits and bool(natural_review.get("quality_passed")),
        "editorial_quality_passed": not editorial_issues and not clarity_issues and not story_issues and not natural_issues,
        "voice_adherence_passed": not voice_issues,
        "clarity_passed": not clarity_issues,
        "story_passed": not story_issues,
        "quality_issue_codes": natural_review.get("quality_issue_codes") or [],
        "quality_rules_version": natural_review.get("quality_rules_version") or "",
        "quality_passed": grounded and score >= 70 and not style_issues,
        "warnings": _content_creative_warnings(text),
        "issues": [
            *(unsupported or []),
            *(["Не указаны источники использованных фактов"] if not used_ids else []),
            *style_issues,
        ],
        "paragraph_count": paragraph_count,
    }

def _content_generation_v2_prompt(
    *,
    business_facts: dict[str, Any],
    brief: dict[str, Any],
    voice: dict[str, Any],
    language: str,
    publication_objective_context: str = "",
    industry_pattern_context: str = "",
    editorial_pattern_context: str = "",
) -> str:
    voice_preferences = voice.get("preferences") if isinstance(voice.get("preferences"), dict) else {}
    business_description = str(voice_preferences.get("business_description") or "").strip()
    audience_description = str(voice_preferences.get("audience_description") or "").strip()
    examples = "\n\n".join(
        f"Пример стиля {index + 1} (НЕ источник фактов текущего поста): {item.get('text')}"
        for index, item in enumerate(voice.get("examples") or [])
    ) or "Примеров пока нет"
    story_source_ids = {
        str(source.get("id") or "")
        for source in brief.get("sources") or []
        if isinstance(source, dict)
        and (str(source.get("id") or "") == "story_facts" or bool(source.get("story_evidence")))
    }
    has_story_facts = bool(story_source_ids)
    story_variant_rule = (
        f"Для человеческой истории используй только эпизод из источников: {', '.join(sorted(story_source_ids))}. "
        "Не добавляй другое имя, возраст, событие или результат. "
        "Если история подробная, сохрани её дугу: исходную сцену, контраст или трудность, решение и последствие; не сворачивай её в рекламное резюме."
        if has_story_facts
        else "Источника story_facts нет: не придумывай героя, имя, возраст, эпизод или результат. "
        "Вместо человеческой истории дай ситуационный вариант без конкретного героя."
    )
    return (
        "Ты — редактор публикаций локального бизнеса. Создай ровно три содержательно разных варианта на основе только перечисленных фактов.\n"
        f"{_content_plan_language_instruction(language)}\n"
        "Варианты: конкретное объяснение, ситуационный подход, спокойный практический подход. "
        "Человеческая история допустима только при наличии явно подтверждённых story_facts. "
        "Не добавляй факты, даты, участников, цены, адреса или обещания, которых нет в источниках. До 700 символов каждый.\n"
        "Редакторские правила для каждого варианта:\n"
        "- одна публикация раскрывает одну главную мысль;\n"
        "- начинай с конкретной ситуации или факта, а не с описания компании и не с рекламного вопроса;\n"
        "- пиши коротко, по делу и именно об этом бизнесе; читатель должен понять каждую фразу без знания маркетингового жаргона;\n"
        "- если в публикации несколько событий, свяжи их в короткий рассказ: общий вход, развитие через переходы во времени или настроении, ясный финал; не выдавай перечень дат и названий;\n"
        "- объясняй механику события обычными словами; не сжимай разные смыслы в метафоры вроде «музыку свайпать» или «выбирать механику»;\n"
        "- используй 1–5 коротких абзацев; текст длиннее 260 символов обязательно разделяй пустой строкой;\n"
        "- не переноси в готовый текст слова «цель публикации», «бизнес-задача», «в фокусе публикации» или другие внутренние инструкции;\n"
        "- не используй хэштеги, рекламные клише и больше одного восклицательного знака;\n"
        "- не копируй источник дословно и не имитируй стиль конкретного автора;\n"
        "- не добавляй масштаб, количество клиентов, возраст, родственную роль, оценку характера или достижение, если этого нет в фактах;\n"
        f"{NATURAL_CONTENT_CONTRACT}\n"
        "- редакционные паттерны ниже описывают только приёмы подачи; не переноси из чужих публикаций факты, героев, названия, цифры или обещания;\n"
        f"- {story_variant_rule}\n"
        "- завершай одним естественным следующим шагом, только если он следует из редакторского брифа.\n"
        "Верни строго JSON: {\"candidates\":[{\"id\":\"variant-1\",\"angle\":\"...\",\"text\":\"...\","
        "\"used_fact_ids\":[\"source_id\"],\"unsupported_facts\":[]}]}\n\n"
        "Факты о бизнесе и услугах находятся в общем снимке источников редакторского брифа ниже.\n\n"
        f"Задача этого типа публикации:\n{publication_objective_context or 'Одна публикация — одна бизнес-задача.'}\n\n"
        f"Правила ниши:\n{industry_pattern_context or 'Нет дополнительных правил.'}\n\n"
        f"Редакционные приёмы из сильных публикаций:\n{editorial_pattern_context or 'Нет дополнительных приёмов.'}\n\n"
        f"Редакторский бриф:\n{_content_brief_prompt_block(brief)}\n\n"
        f"Дополнительный контекст тона от владельца (не новый источник фактов): {business_description or 'нет дополнительного описания'}\n"
        f"Клиенты бизнеса со слов владельца: {audience_description or 'нет дополнительного описания'}\n"
        f"Пожелание пользователя к тону: {voice_preferences.get('tone_instruction') or 'не задано'}. Применяй стиль, не добавляя новых фактов.\n"
        f"Голос бизнеса: {voice.get('summary') or 'спокойный, конкретный, без рекламных клише'}\n"
        f"Запрещённые формулировки: {', '.join(voice.get('forbidden_phrases') or []) or 'нет дополнительных'}\n"
        f"Эталонные публикации — только стиль, НЕ факты текущего поста:\n{examples}\n\n"
        "ОБЯЗАТЕЛЬНЫЕ ГРАНИЦЫ КОНТЕКСТА И ФОРМАТА:\n"
        "Редакторская свобода допустима: образность, тёплый тон, живое начало и эмоциональные формулировки "
        "без гарантии результата. Это не документальный отчёт. Не путай образность с новой услугой, "
        "ценой, персонажем или событием; конкретные сведения по-прежнему требуют источника.\n"
        "1. Тема, цель, SEO-запрос, пожелание к тону и примеры публикаций не подтверждают событие. "
        "Факты для текста берутся только из фактов выбранного бизнеса и источников редакторского брифа. "
        "Чужие примеры не подтверждают услуги, процедуры, цены или результаты этого бизнеса.\n"
        "2. Отзыв подтверждает только дословно описанный случай. Не расширяй его: нельзя придумывать "
        "возраст, мысли, страхи, повторный визит, просьбы ребёнка или диалоги. Не превращай отзыв "
        "в рассказ от первого лица и не выдавай его за личный опыт автора поста. "
        "Если упоминаешь отзыв, явно укажи, что это рассказ клиента, без обещания такого же результата всем.\n"
        "3. Удали каждое утверждение, для которого нет конкретного источника. Не заполняй пробелы "
        "правдоподобными деталями. Каждый used_fact_ids должен быть ID из брифа. "
        "При нехватке фактов верни {\"candidates\":[]} — не выдумывай публикацию.\n"
        "4. Ответ — один валидный JSON-объект с ключом candidates. Используй только двойные кавычки "
        "для ключей и строк; переносы строк внутри text экранируй как \\n. "
        "Никаких Markdown-ограждений, одинарных кавычек, комментариев, префиксов и текста после JSON. "
        "Каждый элемент содержит id, angle, text, used_fact_ids (массив строк), "
        "unsupported_facts (пустой массив). Проверь соответствие формату перед ответом."
    )
