"""Gate a release against a known sidebar rollback, inspecting active modules only."""
from pathlib import Path
import re
import sys


def check(dist: Path) -> None:
    html = (dist / 'index.html').read_text()
    entry = re.search(r'assets/(index-[^"\s]+\.js)', html)
    if not entry:
        raise ValueError('Frontend entry is missing')
    root = (dist / 'assets' / entry.group(1)).read_text()
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
