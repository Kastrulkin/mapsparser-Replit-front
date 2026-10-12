"""Gate a release against a known sidebar rollback, inspecting active modules only."""
from pathlib import Path
import re
import sys


def check_operator(dist: Path) -> None:
    html = (dist / 'index.html').read_text()
    entry = re.search(r'assets/(index-[^"\s]+\.js)', html)
    if not entry: raise ValueError('Frontend entry is missing')
    root = (dist / 'assets' / entry.group(1)).read_text()
    operators = set(re.findall(r'(OperatorPage-[\w.-]+\.js)', root))
    if not operators:
        raise ValueError('Active Operator page is missing')
    for page in operators:
        pending = [page]; seen = {entry.group(1)}; copy = ''
        while pending:
            name = pending.pop()
            if name in seen: continue
            seen.add(name)
            body = (dist / 'assets' / name).read_text()
            copy += body
            pending.extend(re.findall(r'\./([\w.-]+\.js)', body))
        for marker in ['Меню Оператора', 'Текущая задача:', 'К последним сообщениям', 'outreach_result_event_id']:
            if marker not in copy:
                raise ValueError('Outdated Operator: ' + marker)


def check_demo(dist: Path) -> None:
    html = (dist / 'index.html').read_text()
    entry = re.search(r'assets/(index-[^"\s]+\.js)', html)
    if not entry:
        raise ValueError('Frontend entry is missing')
    root = (dist / 'assets' / entry.group(1)).read_text()
    # These sample components are eager imports in App, so inspect the active
    # entry rather than a leftover lazy demo chunk from an earlier release.
    for marker in ['/demo/room', 'demo-coat-care', 'Подтвердить проверку в демо', 'reviewTexts', 'reviewTitle']:
        if marker not in root:
            raise ValueError('Outdated demo: ' + marker)


def check(dist: Path) -> None:
    html = (dist / 'index.html').read_text()
    entry = re.search(r'assets/(index-[^"\s]+\.js)', html)
    if not entry:
        raise ValueError('Frontend entry is missing')
    root = (dist / 'assets' / entry.group(1)).read_text()
    # Check the actual route in the entry, rather than an unrelated newer file
    # left in assets by a previous partial release.
    pages = set(re.findall(r'(PartnershipSearchPage-[\w.-]+\.js)', root))
    if not pages:
        raise ValueError('Active partnerships page is missing')
    for page in pages:
        body = (dist / 'assets' / page).read_text()
        for marker in ['Этапы аутрича', 'Компании', 'Письма', 'search_task_id']:
            if marker not in body:
                raise ValueError('Outdated partnerships page: ' + marker)
        if 'btn-iridescent' not in body and '"brand"' not in body:
            raise ValueError('Missing shared brand treatment in partnerships')
    check_operator(dist)
    check_demo(dist)
    layouts = set(re.findall(r'(DashboardLayout-[\w.-]+\.js)', root))
    if not layouts:
        raise ValueError('Active dashboard layout is missing')
    for layout in layouts:
        text = (dist / 'assets' / layout).read_text()
        for route in ['/dashboard/operator', '/dashboard/partnerships', '/dashboard/influencers', '/dashboard/agents']:
            if route not in text:
                raise ValueError('Missing direct sidebar entry: ' + route)
        seen = {entry.group(1)}
        pending = [layout]
        copy = ''
        while pending:
            name = pending.pop()
            if name in seen:
                continue
            seen.add(name)
            body = (dist / 'assets' / name).read_text()
            copy += body
            pending.extend(re.findall(r'\./([\w.-]+\.js)', body))
        for label in ['Управление через чат', 'Автоматизация']:
            if label not in copy:
                raise ValueError('Outdated sidebar: ' + label)


if __name__ == '__main__':
    try:
        check(Path(sys.argv[1]))
    except (ValueError, OSError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    print('Outreach navigation release check passed')
