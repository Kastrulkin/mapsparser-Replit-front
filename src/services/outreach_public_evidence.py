"""Bounded website evidence for audience qualification; no model-selected URLs."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from core import outbound_network


def collect_candidate_evidence(website: str, terms: list[str]) -> list[dict]:
    parsed = urlparse(website)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        return []
    queue = [website]
    seen = set()
    evidence = []
    for _ in range(3):
        if not queue:
            break
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        response = outbound_network.public_pinned_get(url, headers={"User-Agent": "LocalOS/1.0 public business research"}, timeout=8)
        if 300 <= response.status_code < 400:
            target = urljoin(url, str(response.headers.get("location") or ""))
            if urlparse(target).hostname == parsed.hostname:
                queue.insert(0, target)
            continue
        if response.status_code != 200 or "text/html" not in str(response.headers.get("content-type") or "").lower() or len(response.body) > 1_000_000:
            continue
        soup = BeautifulSoup(response.body, "html.parser")
        for element in soup(["script", "style", "nav", "footer", "form"]):
            element.decompose()
        if len(seen) == 1:
            for link in soup.find_all("a", href=True):
                target = urljoin(url, str(link["href"]))
                if urlparse(target).scheme not in {"http", "https"} or urlparse(target).hostname != parsed.hostname:
                    continue
                label = (link.get_text(" ", strip=True) + " " + target).casefold()
                if terms and any(term.casefold() in label for term in terms) and target not in queue:
                    queue.append(target)
                    if len(queue) >= 2:
                        break
        lines = [" ".join(text.split()) for text in soup.stripped_strings]
        matching = [text for text in lines if 20 <= len(text) <= 1200 and (not terms or any(term.casefold() in text.casefold() for term in terms))]
        for text in matching[:6]:
            evidence.append({"id": hashlib.sha256((url + text).encode()).hexdigest()[:24],
                "fact": text, "source_url": url, "source_type": "public_website",
                "observed_at": datetime.now(timezone.utc).isoformat(), "freshness": "current_snapshot", "confidence": 0.8})
    return evidence
