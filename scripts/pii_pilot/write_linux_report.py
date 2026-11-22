"""Render the dated Linux/Redis evidence; original pilot results remain historical."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = ROOT / "docs/pii-protection/results/linux-20261102"


def main():
    verification = json.loads((DIRECTORY / "verification.json").read_text())
    redis = json.loads((DIRECTORY / "redis-performance.json").read_text())
    reports = [json.loads((DIRECTORY / "comparison" / f"{engine}-{profile}.json").read_text())
               for engine in ("piighost_presidio", "preserve") for profile in ("native", "localos_rules")]
    assert all(report["corpus_sha256"] == verification["corpus_sha256"] for report in reports)
    assert redis["environment"]["target_2cpu_4gb_measured"]
    selected = [report for report in reports if report["profile"] == "localos_rules"]
    env = redis["environment"]
    lines = ["# PII: исправления имён и проверка Linux / Redis", "",
             "Статус: `internal`, проверено 02.11.2026. Флаг `PII_PROTECTION_ENABLED` остаётся выключенным по умолчанию.",
             "Production, реальные данные и внешние LLM не использовались. Все HTTP-провайдеры — локальные имитации.", "",
             "## Результат", "",
             "Оба адаптированных кандидата защищают все 290 размеченных значений в исходных 200 сценариях и сохраняют все 10 публичных названий/адресов с серверным контекстом.",
             "Для LocalOS сохранён piighost + Presidio: сопоставимое качество на этом наборе при существенно меньшей задержке и меньшем числе лишних детекций.",
             f"Итоговый Linux-прогон: **{verification['tests']['passed']} passed, 0 failed, 0 skipped**.", "",
             "## Что изменилось", "",
             "1. Добавлены контекстные PERSON-диапазоны рядом с намерением записаться, перенести встречу или связаться. Они охватывают арабские и смешанные написания; найденное точное имя защищается и в повторных упоминаниях текущего текста.",
             "2. Исключения для публичных названий/адресов стали позиционными: PublicSpan привязан к бизнесу, source_id, типу и точному диапазону в окончательном prompt. Такое же имя вне диапазона остаётся защищённым.",
             "3. Снято прежнее общее исключение ORG/LOCATION по одному лишь public_geo/content. Надпись Company в недоверенном тексте не придаёт данным публичный статус.",
             "4. Частные явно обозначенные имя/адрес и критические форматы не освобождаются от защиты даже внутри разрешённого публичного диапазона. Некорректный scope, диапазон, тип и JSON-объект вместо серверного PublicSpan блокируют запрос.", "",
             "Контекст публичности — новый вход со стороны доверенного сборщика prompt, а не распознавание правды по строке. Gateway проверяет привязку и границы; источник и права доступа к нему обязан проверить серверный caller. Само наличие source_id не является DB-проверкой.",
             "В пилоте этот вход представлен отдельными синтетическими записями `tests/fixtures/pii/public_context.json`. Разметка частных имён и ожидаемых сущностей детекторам не передаётся. Автозагрузка источников из production-БД не выполнялась.", "",
             "## Сравнение на том же корпусе", "",
             "Корпус не изменён: 200 сценариев, 290 значений, RU 60 / EN 40 / TR 40 / DE 20 / AR 20 / mixed 20.",
             f"SHA-256: `{verification['corpus_sha256']}`.",
             "В отличие от первого пилота добавлен самостоятельный серверный вход публичных диапазонов. Результаты public_geo относятся к наличию этого подтверждённого контекста; глобальной allowlist строк нет.", "",
             "| Кандидат / профиль | Защищено | Recall | Overlap precision | Критические пропуски | Ложные детекции | Полностью защищено | Round-trip | Public geo | p95, мс |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for report in reports:
        total = report["totals"]
        lines.append(f"| {report['engine']} / {report['profile']} | {total['protected']}/290 | {total['recall']:.2%} | {total['precision']:.2%} | {total['critical_missed']} | {total['false_positives']} | {report['fully_protected_messages']}/200 | {report['round_trip_exact_messages']}/200 | {report['public_geo_preserved']}/10 | {report['performance']['p95_ms']} |")
    lines += ["", "Recall требует покрытия полного диапазона и отсутствия оригинала в отправляемом тексте. Precision — доля детекций, пересекающих размеченную сущность; это не exact-span/type NER precision.",
              "Round-trip в сравнении обратим, включая тестовые секреты; runtime намеренно не сохраняет секреты в mapping и не восстанавливает их.",
              "Четыре дополнительные детекции у выбранного варианта остаются вне публичных geo-контролей; ноль ложных срабатываний вообще не заявляется.", "",
              "| Язык | piighost + Presidio | Preserve |", "|---|---:|---:|"]
    for language in ("ru", "en", "tr", "de", "ar", "mixed"):
        left, right = [report["by_language"][language] for report in selected]
        lines.append(f"| {language} | {left['protected']}/{left['expected']} | {right['protected']}/{right['expected']} |")
    lines += ["", "## Linux и настоящий Redis", "",
              f"Локальный Docker: {env['os']} / {env['machine']} / Python {env['python']}; Redis {redis['redis_version']}.",
              f"Проверенные cgroup-лимиты: {env['cpu_quota_cores']} CPU и {env['memory_limit_bytes']} байт (4 GiB), swap сверх этого не разрешён.",
              "Контейнер имеет network=none; разрешён только его loopback. Redis привязан к 127.0.0.1:16379, без публикации порта, RDB/AOF и внешних томов.",
              "Из checkout переданы только явно перечисленные исходники и синтетические fixtures. .env, production конфигурация, файлы клиентов и Docker socket в контейнер не передавались.", "",
              "Полный слой измерен с HMAC, Fernet, фактическими Redis SET/GET и восстановлением: 200 прогревочных запросов, затем 600 последовательных и 600 запросов от четырёх клиентов; NLP-полоса одна.", "",
              "| Режим | p50, мс | p95, мс | p99, мс | запросов/с |", "|---|---:|---:|---:|---:|"]
    lines += [f"| Последовательно | {redis['p50_ms']} | {redis['p95_ms']} | {redis['p99_ms']} | {redis['requests_per_second']} |",
              f"| 4 клиента | {redis['concurrent_p50_ms']} | {redis['concurrent_p95_ms']} | {redis['concurrent_p99_ms']} | {redis['concurrent_requests_per_second']} |", "",
              f"RSS Python: {redis['python_rss_bytes']/1048576:.1f} MiB; Redis: {redis['redis_rss_bytes']/1048576:.1f} MiB; пик cgroup: {redis['cgroup_peak_bytes']/1048576:.1f} MiB.",
              f"CPU на прогрев + оба измеряемых этапа: Python {redis['cpu_python_seconds']} с, Redis {redis['cpu_redis_seconds']} с.",
              "Это Linux/ARM64 под CPU-квотой, а не замер production-сервера, его архитектуры и всего LocalOS-стека. Долгий soak, полный состав app/worker и нагрузка остальных сервисов не проверялись.", "",
              "## Проверки и воспроизведение", "",
              "Проверены все 200 сценариев на фактической HTTP-границе каждого адаптера с MemoryStore и с настоящим Redis; исходящий JSON декодируется перед проверкой отсутствия оригиналов.",
              "Дополнительно пройдены 13 вариантов новых написаний имён, позиционные публичные исключения, чужой tenant, поддельные метаданные, private labels/контакты внутри публичного диапазона, expiry/corruption настоящего Redis, чтение другим процессом, 32 параллельных сессии и отказ соединения до запроса провайдеру.",
              "Тесты инструментов, approvals, recovery retry, streaming, JSON и default-off также пройдены. Hosted CI подготовлен, но не запускался.",
              "Перед исправлением исходные пять ошибок воспроизведены: [red](results/linux-20261102/red.json). Финальный результат: [green](results/linux-20261102/green.json), [verification](results/linux-20261102/verification.json).",
              "Манифесты сравнения и финальной проверки сохранены отдельно: после сравнения усилены проверки типов метаданных; правила имён и диапазонов остаются теми же.", "",
              "## Оставшиеся ограничения", "",
              "- Контекстные правила закрывают проверенные конструкции; общая точность произвольной арабской/смешанной речи, нижнего регистра и неоднозначных имён не доказана.",
              "- Публичные диапазоны нужно собирать из реально проверенных записей LocalOS. При отсутствии контекста система сохраняет консервативную защиту; автоматически доверять подписи Company запрещено.",
              "- Synthetic корпус использует повторяющиеся семейства значений и не заменяет независимую оценку на расширенном обезличенном материале.",
              "- Неподдержанные изображения, embeddings и legacy-маршруты при включении защиты продолжают блокироваться; live API/ACL/production egress не проверялись.",
              "- Прежнее отдельное расхождение tests/test_llm_routing.py по photo_analysis этим исправлением не менялось; полный проектный CI не заявляется зелёным.", "",
              "Флаг остаётся выключенным. Синтетические результаты не доказывают полную анонимность или юридическое соответствие.",
              "[Установка и команды Linux](deployment.md) · [Архитектура](architecture.md) · [Исходный пилот 01.11.2026](benchmark-20261101.md)"]
    (ROOT / "docs/pii-protection/benchmark.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
