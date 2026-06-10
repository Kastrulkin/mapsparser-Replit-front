#!/usr/bin/env python3
"""Guard first-layer copy on the LocalOS agents screen."""

from pathlib import Path
import re
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_PAGE = REPO_ROOT / "frontend" / "src" / "pages" / "dashboard" / "AgentBlueprintsPage.tsx"

FORBIDDEN_VISIBLE_PHRASES = {
    "Preview run": "use 'Проверить на примере'",
    "Preview будущего": "use 'Проверка будущего агента'",
    "Создать из preview": "use 'Создать после проверки'",
    "capability не подключена": "explain the missing action in user language",
    "credentials required": "use 'Нужен доступ ...'",
    "approved external write": "use 'Запись после подтверждения'",
    "runtime truth": "use 'активная логика'",
    "Legacy workflow": "use 'старая логика'",
    "workflow debugger": "do not present the screen as a debugger",
    "Learning Loop": "use 'Улучшение версии'",
    "versioned learning": "use 'версионное улучшение'",
    "Плохой outcome": "use 'Плохой результат'",
    "Feedback применён": "use 'Обратная связь применена'",
    "Feedback": "use 'Обратная связь' in visible copy",
    "Rollback": "use 'Откат'",
    "Version event": "use 'Событие версии'",
    "Learning event": "use 'Событие обучения'",
    "extraction, processing": "use user-facing Russian copy",
    "destructive actions": "use 'опасные изменения'",
}


def extract_visible_fragments(text: str) -> list[str]:
    fragments = []
    string_pattern = re.compile(r"""(['"`])((?:\\.|(?!\1).)*)\1""")
    jsx_text_pattern = re.compile(r">([^<>{}][^<]*)<")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("import ") or stripped.startswith("type "):
            continue
        for match in string_pattern.finditer(line):
            fragments.append(match.group(2))
        for match in jsx_text_pattern.finditer(line):
            value = " ".join(match.group(1).split())
            if value:
                fragments.append(value)
    return fragments


def main() -> int:
    text = AGENTS_PAGE.read_text(encoding="utf-8")
    visible_text = "\n".join(extract_visible_fragments(text))
    failures = []
    for phrase, guidance in FORBIDDEN_VISIBLE_PHRASES.items():
        if phrase in visible_text:
            failures.append((phrase, guidance))

    if failures:
        print("Agents product UI copy guard failed:")
        for phrase, guidance in failures:
            print(f"- {phrase!r}: {guidance}")
        return 1

    print("OK: agents product UI first-layer copy guard passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
