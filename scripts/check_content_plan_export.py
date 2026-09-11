"""Generate a Cyrillic, multi-page export fixture for visual release checks."""
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from services.content_plan_export import render_export

if __name__ == '__main__':
    destination = Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=True)
    plan = {'title': 'Контент-план на сентябрь', 'scope_target_label': 'Органика / две точки', 'period_start': '2026-09-01', 'period_end': '2026-09-30', 'items': [
        {'scheduled_for': datetime(2026, 9, 12, tzinfo=timezone.utc), 'theme': 'Как подготовиться к массажу', 'goal': 'Объяснить клиенту подготовку', 'draft_text': ('Расскажите специалисту о ваших пожеланиях. Выберите удобное время для посещения.\n' * 120), 'status': 'draft_generated', 'location_label': 'Центр', 'source_ref': 'https://example.com/material'},
        {'theme': 'Знакомство с командой', 'goal': 'Идея, текст ещё не подготовлен', 'location_label': 'Вторая точка', 'status': 'planned'},
    ]}
    (destination / 'content-plan.pdf').write_bytes(render_export(plan, 'pdf').getvalue())
    (destination / 'content-plan.xlsx').write_bytes(render_export(plan, 'xlsx').getvalue())
    print(destination)
