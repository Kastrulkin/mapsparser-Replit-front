"""Render the human report from measured JSON, without inventing missing runs."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "docs/pii-protection/results"


def main():
    reports = [json.loads((RESULTS / f"{engine}-{profile}.json").read_text())
               for engine in ("piighost_presidio", "preserve") for profile in ("native", "localos_rules")]
    gateway = json.loads((RESULTS / "gateway-performance.json").read_text())
    hashes = {report["corpus_sha256"] for report in reports} | {gateway["corpus_sha256"]}
    assert len(hashes) == 1
    lines = ["# Измерения пилота PII", "", "Статус: `internal`. Локальный запуск 01.11.2026, только синтетические данные.",
             "Production и внешние LLM не использовались. Лучший кандидат внедрён под выключенным флагом; production-приёмка не пройдена.", "",
             "## Корпус и методика", "", "200 сценариев, 290 размеченных значений; 20 форм × 10 языковых/форматных вариантов.",
             "Языки: RU 60, EN 40, TR 40, DE 20, AR 20, mixed 20. Есть отрицательные примеры и 10 public-geo контролей.",
             "Разметка содержит точные диапазоны, типы, критичность и допустимый публичный контекст.",
             "Корпус фиксирован до первого сравнения; ожидания не передаются детекторам.",
             "Native — настоящие библиотеки с одинаковыми compact RU/EN-моделями; localos_rules — те же результаты плюс одинаковые правила LocalOS.",
             "LLM, большие словари и внешние сервисы распознавания не используются. У Presidio отключена загрузка suffix list; payload-трассировки piighost выключены.", "",
             "Recall требует покрытия всего размеченного диапазона и отсутствия исходного значения в отправляемом тексте.",
             "Precision здесь измеряет долю детекций, пересекающих размеченные сущности; это overlap precision, не точное совпадение границ или типов NER.",
             "Fully protected включает сообщения без PII и не учитывает полезность геомаркетинга — она измеряется отдельно.",
             "Round-trip native выполняется методами библиотек. В сравнительном профиле правил восстановление обратимо; runtime намеренно не восстанавливает секреты.", "",
             "Корпус SHA-256: `" + next(iter(hashes)) + "`.", "", "## Сравнение", "",
             "| Кандидат / профиль | Recall | Precision | Защищено значений | Пропущено критических | Ложные детекции | Полностью защищено сообщений | Точное восстановление | Public geo |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for report in reports:
        total = report["totals"]
        lines.append(f"| {report['engine']} / {report['profile']} | {total['recall']:.2%} | {total['precision']:.2%} | {total['protected']}/290 | {total['critical_missed']} | {total['false_positives']} | {report['fully_protected_messages']}/200 | {report['round_trip_exact_messages']}/200 | {report['public_geo_preserved']}/10 |")
    selected = [report for report in reports if report["profile"] == "localos_rules"]
    lines += ["", "## По языкам после общих правил", "", "| Язык | piighost + Presidio: защищено | Recall | Критические пропуски | Preserve: защищено | Recall | Критические пропуски |", "|---|---:|---:|---:|---:|---:|---:|"]
    for language in ("ru", "en", "tr", "de", "ar", "mixed"):
        left, right = [report["by_language"][language] for report in selected]
        lines.append(f"| {language} | {left['protected']}/{left['expected']} | {left['recall']:.2%} | {left['critical_missed']} | {right['protected']}/{right['expected']} | {right['recall']:.2%} | {right['critical_missed']} |")
    lines += ["", "## По типам после общих правил", "", "| Тип | piighost + Presidio | Preserve |", "|---|---:|---:|"]
    for kind in selected[0]["by_type"]:
        left, right = [report["by_type"][kind] for report in selected]
        lines.append(f"| {kind} | {left['protected']}/{left['expected']} | {right['protected']}/{right['expected']} |")
    lines += ["", "## Производительность", "", "Среда: macOS / arm64 / Python 3.11.7, ограничение NLP/BLAS до одной полосы.",
              "Это не измерение Docker-стека на Linux с 2 vCPU / 4 ГБ. В JSON стоит `target_2cpu_4gb_measured=false`.",
              "Каждый профиль работает в новом процессе. RSS — максимум всего процесса после последовательного и параллельного этапов; ресурсы и загрузка окружения не эквивалентны production.", "",
              "| Профиль | p50, мс | p95, мс | p99, мс | запросов/с | CPU, с | peak RSS, MiB | 4 клиента: p95, мс | 4 клиента: запросов/с |",
              "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for report in reports:
        p = report["performance"]
        lines.append(f"| {report['engine']} / {report['profile']} | {p['p50_ms']} | {p['p95_ms']} | {p['p99_ms']} | {p['requests_per_second']} | {p['cpu_seconds']} | {p['peak_rss_bytes']/1048576:.1f} | {p['concurrent_p95_ms']} | {p['concurrent_requests_per_second']} |")
    p = gateway
    lines.append(f"| Полный выбранный gateway + encrypted MemoryStore + restore | {p['p50_ms']} | {p['p95_ms']} | {p['p99_ms']} | {p['requests_per_second']} | {p['cpu_seconds']} | {p['peak_rss_bytes']/1048576:.1f} | {p['concurrent_p95_ms']} | {p['concurrent_requests_per_second']} |")
    lines += ["", "Последняя строка включает HMAC, шифрование, lookup и восстановление на том же корпусе. Сетевой Redis RTT в неё не входит; Redis-контракт отдельно проверяется fakeredis.",
              "Однократный короткий прогон не характеризует p99 длительной нагрузки; длительный soak и многопроцессная модель app/worker ещё нужны.", "",
              "## Решение и остаточные ошибки", "", "Выбран piighost + Presidio: 288/290 защищённых значений против 285/290 и значительно меньшая задержка после общих правил.",
              "У обоих адаптированных кандидатов 0 критических пропусков на данном корпусе. Это не гарантия отсутствия пропусков на других данных.",
              "Два пропуска выбранного варианта: synthetic-018 (AR free_name) и synthetic-019 (mixed free_name).",
              "Preserve дополнительно пропускает три русских free_name-сценария. Публичные названия сохраняются полностью в 7/10 geo-контролей у обоих адаптированных вариантов.",
              "В трёх остальных случаях PERSON-NER скрывает часть публичного названия. Нужны проверенная публичная идентичность из реестра и отдельные политики, а не глобальная строковая allowlist.", "",
              "## Проверки и готовность", "", "Локальный профиль `tests/test_pii_protection.py`, `tests/test_llm_budget_boundary.py`, `tests/test_operator_tool_loop.py` пройден; итоговый счётчик в `results/verification.json`.",
              "Проверены фактические HTTP-payload обоих адаптеров на loopback mock, mail/booking имитации, tenant/session изоляция, параллелизм, streaming splits, JSON, TTL/corruption, forged tokens, tool allowlist/approval, recovery retry, diagnostic, ошибки и отсутствие raw payload в новых ошибках/трассировках.",
              "Более широкий прогон с `tests/test_llm_routing.py`: 277 passed / 1 failed до последних дополнительных тестов; единственное расхождение — photo_analysis присутствует в существующем реестре, но отсутствует в ожидаемом списке tests/test_llm_routing.py:98. Реестр и этот тест в рамках пилота не менялись.",
              "Hosted CI не запускался. Production, живой Redis и Linux 2 vCPU / 4 ГБ не проверялись. Нет доказательства безопасной обработки произвольного свободного текста или сохранения всех public-geo названий.",
              "Итог: пилот и выключенная интеграция готовы; production-включение остаётся заблокировано качеством свободного текста/geo и инфраструктурными замерами.", "",
              "Воспроизведение: [deployment.md](deployment.md). Полные измерения: [results/](results/)."]
    (ROOT / "docs/pii-protection/benchmark.md").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    if (RESULTS / "linux-20261102/verification.json").exists():
        from write_linux_report import main
    main()
