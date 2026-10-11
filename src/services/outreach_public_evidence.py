"""Bounded website evidence for audience qualification; no model-selected URLs."""
from __future__ import annotations

import hashlib
import logging
from urllib3.exceptions import HTTPError
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from core import outbound_network


def collect_candidate_evidence(website: str, terms: list[str], *, requirements: list[str] | None = None) -> list[dict]:
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
        try:
            response = outbound_network.public_pinned_get(url, headers={"User-Agent": "LocalOS/1.0 public business research"}, timeout=8)
        except (HTTPError, ValueError, OSError, TimeoutError) as exc:
            logging.getLogger(__name__).warning("Public evidence page unavailable: %s", type(exc).__name__)
            continue
        if 300 <= response.status_code < 400:
            target = urljoin(url, str(response.headers.get("location") or ""))
            if urlparse(target).hostname == parsed.hostname:
                queue.insert(0, target)
            continue
        if response.status_code != 200 or "text/html" not in str(response.headers.get("content-type") or "").lower() or len(response.body) > 1_000_000:
            continue
        soup = BeautifulSoup(response.body, "html.parser")
        # Discover links before removing navigation. Menus often contain the
        # product/service pages needed to prove a requirement.
        if len(seen) == 1:
            candidates = []
            for link in soup.find_all("a", href=True):
                target = urljoin(url, str(link["href"]))
                if urlparse(target).scheme not in {"http", "https"} or urlparse(target).hostname != parsed.hostname:
                    continue
                label = (link.get_text(" ", strip=True) + " " + target).casefold()
                score = sum(term.casefold() in label for term in terms if term.strip()) * 10
                score += sum(term in label for term in ('service', 'product', 'about', 'contact', 'услуг', 'товар', 'контакт', 'о нас'))
                if requirements is not None:
                    score += sum(term.casefold() in label for term in requirements if term.strip()) * 10
                if score and target not in seen:
                    candidates.append((score, target))
            ranked = sorted(candidates, key=lambda item: -item[0])
            contact = next((target for _, target in ranked if any(word in target.casefold() for word in ('contact', 'about', 'контакт'))), None)
            selected = [target for _, target in ranked]
            if contact and selected and contact != selected[0]:
                selected = [selected[0], contact]
            for target in selected:
                if target not in queue:
                    queue.append(target)
                if len(queue) >= 2:
                    break
        # Public footer addresses are evidence too; only executable/form and
        # navigation noise is removed from the source text.
        for element in soup(["script", "style", "nav", "form"]):
            element.decompose()
        lines = [" ".join(text.split()) for text in soup.stripped_strings]
        chunks, current = [], ""
        for line in lines:
            if len(current) + len(line) > 900 and current:
                chunks.append(current)
                current = ""
            current = (current + " " + line).strip()
        if current:
            chunks.append(current)
        matching = [text for text in chunks if 20 <= len(text) <= 1200]
        ranked_text = sorted(matching, key=lambda text: -sum(term.casefold() in text.casefold() for term in terms if term.strip()))
        matching = list(dict.fromkeys([*ranked_text[:5], *matching[-3:]]))
        for text in matching[:8]:
            evidence.append({"id": hashlib.sha256((url + text).encode()).hexdigest()[:24],
                "fact": text, "source_url": url, "source_type": "public_website",
                "observed_at": datetime.now(timezone.utc).isoformat(), "freshness": "current_snapshot", "confidence": 0.8})
    return evidence
