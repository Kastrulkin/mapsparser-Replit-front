"""Reject frontend artifacts that cannot open MAX content links."""

import re
import sys
from pathlib import Path


def check(dist):
    root = Path(dist)
    html = (root / "index.html").read_text()
    entries = re.findall(r'src="(/assets/index-[^"]+\.js)"', html)
    if not entries:
        raise ValueError("Frontend entry is missing")
    entry = (root / entries[0].lstrip("/")).read_text()
    if "/max/control" not in entry:
        raise ValueError("Published entry has no /max/control route")
    scripts = "\n".join(file.read_text() for file in (root / "assets").glob("*.js"))
    for required in ("st.max.ru/js/max-web-app.js", "WebAppStartParam", "resolved_deep_link", "focusItemId"):
        if required not in scripts:
            raise ValueError(f"MAX content navigation support is missing: {required}")
    print("MAX route, SDK and content navigation: OK")


if __name__ == "__main__":
    check(sys.argv[1] if len(sys.argv) > 1 else "frontend/dist")
