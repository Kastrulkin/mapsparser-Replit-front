"""Stage a minimal patch against the inspected production content module.

Does not replace running files or restart services. Avoids overwriting newer
content voice, revisions, menu and other production behavior with an old tree.
"""
import hashlib
from pathlib import Path

EXPECTED = 'df704e3bc7393c276715d5a1a2107a9c41927af0001ec91957bc76a5a1451237'


def stage():
    target = Path('/opt/seo-app/src/services/content_plan_service.py')
    original = target.read_text()
    if hashlib.sha256(target.read_bytes()).hexdigest() != EXPECTED:
        raise SystemExit('Production changed; candidate not staged')
    changes = [
        ('def _content_plan_business_facts(business_row: Any, item: dict[str, Any]) -> dict[str, Any]:',
         'def _content_plan_business_facts(business_row: Any, item: dict[str, Any], website_source=None) -> dict[str, Any]:'),
        ('    site_description = _fetch_site_description(website_url)',
         '    if website_source:\n        from services.openclaw_website_reader import website_material\n'
         '        site_description = website_material(website_source)\n    else:\n'
         '        site_description = _fetch_site_description(website_url)'),
        ('        "site_description": site_description,',
         '        "site_description": site_description,\n        "website_source": website_source or {},'),
        ('        business_facts = _content_plan_business_facts(business_row, item)',
         "        from services.openclaw_website_reader import read_business_website\n"
         "        website_url = _normalize_website_url(\n"
         "            _row_get(business_row, 'site', 7, '') or _row_get(business_row, 'website', 8, '')\n        )\n"
         "        website_source = read_business_website(\n"
         "            cursor, user_id, str(item.get('business_id') or ''), website_url\n"
         "        ) if website_url else None\n"
         '        business_facts = _content_plan_business_facts(business_row, item, website_source)'),
        ('        generation_metadata = {',
         '        generation_metadata = {\n            "website_source": business_facts.get("website_source") or {},'),
        ('            "generation": {\n                "success": generation_source == "ai",',
         '            "generation": {\n                "website_source": business_facts.get("website_source") or {},\n'
         '                "success": generation_source == "ai",'),
    ]
    candidate = original
    for before, after in changes:
        if candidate.count(before) != 1:
            raise SystemExit('Unexpected content module structure; no runtime files changed')
        candidate = candidate.replace(before, after, 1)
    compile(candidate, str(target), 'exec')
    folder = Path('/opt/seo-app/backups/openclaw-web-read-candidate')
    folder.mkdir(mode=0o700, exist_ok=True)
    (folder / 'content_plan_service.before.py').write_text(original)
    (folder / 'content_plan_service.candidate.py').write_text(candidate)
    print('Candidate compiled; running content module unchanged')


if __name__ == '__main__':
    stage()
