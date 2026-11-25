"""Run the installed SEOmator checks on HTML collected by LocalOS."""
import json
import logging
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


IMAGE_RUNNER = Path('/opt/localos/website-seo/audit.mjs')
LOCAL_RUNNER = Path(__file__).resolve().parents[1] / 'website_seo' / 'audit.mjs'
logger = logging.getLogger(__name__)


def unavailable(note):
    return {'status': 'unavailable', 'note': note}


def audit_pages(pages):
    if not pages:
        return unavailable('Для SEO-проверки нужна доступная HTML-страница. Проверьте ссылку и повторите.')
    binary = shutil.which('node')
    runner = IMAGE_RUNNER if IMAGE_RUNNER.is_file() else LOCAL_RUNNER
    if not binary:
        return unavailable('SEO-проверка временно недоступна. Можно повторить позже.')
    try:
        result = subprocess.run(
            [binary, '--max-old-space-size=192', str(runner)],
            input=json.dumps(pages, ensure_ascii=False), capture_output=True,
            check=True, timeout=12, encoding='utf-8', env={'LANG': 'C.UTF-8'},
        )
        audited = json.loads(result.stdout)
        if not isinstance(audited, list) or len(audited) != len(pages):
            raise ValueError('Incomplete website audit')
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        logger.warning('Website SEOmator audit failed (%s)', type(error).__name__)
        return unavailable('SEO-проверка не завершилась. Можно повторить позже.')
    return {
        'status': 'ready', 'engine': 'SEOmator', 'pages': audited,
        'checked_at': datetime.now(timezone.utc).isoformat(),
    }
