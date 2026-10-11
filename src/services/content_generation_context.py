"""Reuse content-plan editorial inputs for chat generation; never retrieve secrets."""
import json
import psycopg2
from core.industry_patterns import detect_industry_key, format_industry_pattern_prompt
from core.industry_pattern_recalibration import load_active_industry_patterns, format_loaded_active_industry_patterns
from services import content_plan_service
from services.content_voice_service import load_content_voice_context


def generation_context(cursor, *, business_id, user_id, business, item):
    metadata = {'schema': 'editorial_context_v1', 'reference_ids': [], 'missing_inputs': []}
    def read(name, loader, default):
        cursor.execute('SAVEPOINT editorial_context_input')
        try:
            value = loader()
            if getattr(cursor.connection, 'get_transaction_status', lambda: None)() == psycopg2.extensions.TRANSACTION_STATUS_INERROR:
                cursor.execute('ROLLBACK TO SAVEPOINT editorial_context_input')
                metadata['missing_inputs'].append(name)
                value = default
        except (psycopg2.errors.UndefinedTable, psycopg2.errors.UndefinedColumn):
            cursor.execute('ROLLBACK TO SAVEPOINT editorial_context_input')
            metadata['missing_inputs'].append(name)
            value = default
        except Exception:
            cursor.execute('ROLLBACK TO SAVEPOINT editorial_context_input')
            raise
        finally:
            cursor.execute('RELEASE SAVEPOINT editorial_context_input')
        return value
    def business_identity():
        cursor.execute('SELECT business_type, industry, categories FROM businesses WHERE id=%s', (business_id,))
        return content_plan_service._row_to_dict(cursor, cursor.fetchone())
    identity = read('business_industry', business_identity, {})
    industry = detect_industry_key(business_name=business.get('name'), business_type=identity.get('business_type') or business.get('business_type'),
        industry=identity.get('industry') or business.get('industry'), categories=identity.get('categories') or business.get('categories'),
        service_text=business.get('description'))
    voice = read('voice', lambda: load_content_voice_context(cursor, user_id=user_id, business_id=business_id), {})
    patterns = read('industry_patterns', lambda: load_active_industry_patterns(cursor.connection, industry, 'news'), [])
    references = read('publication_examples', lambda: content_plan_service._load_editorial_pattern_library(cursor, item, industry_key=industry), [])
    demand = read('search_demand', lambda: content_plan_service._fetch_seo_keywords(cursor, user_id, business_id), [])
    topic_tokens = content_plan_service._tokenize_content_plan_topic(' '.join(str(item.get(key) or '') for key in ('theme', 'goal')))
    demand = [value for value in demand if topic_tokens & content_plan_service._tokenize_content_plan_topic(value.get('keyword'))]
    facts = read('company_evidence', lambda: content_plan_service._load_business_content_evidence(cursor, {**item, 'business_id': business_id}, limit=6), [])
    metadata.update(industry=industry, reference_ids=[value['id'] for value in references],
                    voice_example_ids=[value['id'] for value in voice.get('examples') or []],
                    voice_version=voice.get('version'), keywords=[value['keyword'] for value in demand[:10]])
    blocks = [
        'Подтверждённые данные компании (не заменяй их фактами из чужих постов):\n'+json.dumps(facts, ensure_ascii=False, default=str),
        'Назначение публикации:\n'+content_plan_service._publication_objective_prompt_block(industry, item),
        'Правила отрасли:\n'+format_industry_pattern_prompt(industry, mode='news')+'\n'+format_loaded_active_industry_patterns(patterns),
        'Приёмы из релевантных публикаций Telegram и карт:\n'+content_plan_service._format_editorial_pattern_context(references),
        'Утверждённые примеры и голос бизнеса. Это образцы стиля, не источник новых фактов:\n'+json.dumps(voice, ensure_ascii=False, default=str),
        'Сохранённые запросы Wordstat: это не доказательство роста спроса или текущей региональной частотности. Используй только уместный запрос естественно, не набивай текст ключами:\n'+json.dumps(demand[:10], ensure_ascii=False),
    ]
    return '\n\n'.join(blocks), metadata
