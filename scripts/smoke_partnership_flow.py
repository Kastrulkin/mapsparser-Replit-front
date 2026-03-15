#!/usr/bin/env python3
"""
End-to-end smoke for partnership pipeline.

Flow:
1) import link
2) list leads + pick lead
3) parse
4) audit
5) match
6) draft offer
7) approve draft
8) create batch
9) approve batch
10) record reaction/outcome
11) health snapshot

Usage example:
  AUTH_TOKEN="<jwt>" \
  BUSINESS_ID="<uuid>" \
  MAP_URL="https://yandex.ru/maps/org/1221240931/" \
  python3 scripts/smoke_partnership_flow.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass
class StepResult:
    name: str
    ok: bool
    http_status: int | None = None
    detail: str | None = None
    data: dict[str, Any] | None = None


class SmokeFailure(RuntimeError):
    pass


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _api_call(
    base_url: str,
    path: str,
    token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 60,
) -> tuple[int, dict[str, Any]]:
    url = f"{base_url.rstrip('/')}{path}"
    body = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            data = json.loads(raw) if raw else {}
            return int(resp.status), data
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            data = json.loads(raw) if raw else {}
        except Exception:
            data = {"raw": raw}
        return int(exc.code), data


def _run_step(
    steps: list[StepResult],
    name: str,
    fn,
    fatal: bool = True,
) -> dict[str, Any]:
    try:
        status, data = fn()
        ok = 200 <= status < 300
        detail = None if ok else str(data.get("error") or data)[:400]
        step = StepResult(name=name, ok=ok, http_status=status, detail=detail, data=data if ok else None)
        steps.append(step)
        if fatal and not ok:
            raise SmokeFailure(f"{name} failed: HTTP {status} {detail}")
        return data if ok else {}
    except SmokeFailure:
        raise
    except Exception as exc:
        steps.append(StepResult(name=name, ok=False, http_status=None, detail=str(exc)[:400], data=None))
        if fatal:
            raise SmokeFailure(f"{name} exception: {exc}") from exc
        return {}


def _pick_lead_id(items: list[dict[str, Any]], source_url: str) -> str | None:
    normalized = source_url.strip().lower()
    for item in items:
        if str(item.get("source_url") or "").strip().lower() == normalized:
            lead_id = str(item.get("id") or "").strip()
            if lead_id:
                return lead_id
    if items:
        lead_id = str(items[0].get("id") or "").strip()
        if lead_id:
            return lead_id
    return None


def _pick_draft_id(drafts: list[dict[str, Any]], lead_id: str) -> str | None:
    for item in drafts:
        if str(item.get("lead_id") or "").strip() == lead_id:
            return str(item.get("id") or "").strip() or None
    if drafts:
        return str(drafts[0].get("id") or "").strip() or None
    return None


def _pick_batch_id(batches: list[dict[str, Any]]) -> str | None:
    if not batches:
        return None
    return str(batches[0].get("id") or "").strip() or None


def _pick_queue_id(batch_item: dict[str, Any] | None) -> str | None:
    if not isinstance(batch_item, dict):
        return None
    queue_items = batch_item.get("items")
    if not isinstance(queue_items, list) or not queue_items:
        return None
    return str(queue_items[0].get("id") or "").strip() or None


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke partnership flow and export JSON report.")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://localhost:8000"))
    parser.add_argument("--token", default=os.getenv("AUTH_TOKEN", ""))
    parser.add_argument("--business-id", default=os.getenv("BUSINESS_ID", ""))
    parser.add_argument("--map-url", default=os.getenv("MAP_URL", ""))
    parser.add_argument("--lead-name", default=os.getenv("LEAD_NAME", f"partnership-smoke-{int(time.time())}"))
    parser.add_argument("--report", default=os.getenv("REPORT_PATH", ""))
    parser.add_argument("--timeout", type=int, default=int(os.getenv("SMOKE_TIMEOUT_SEC", "90")))
    args = parser.parse_args()

    if not args.token:
        print("AUTH_TOKEN is required", file=sys.stderr)
        return 2
    if not args.business_id:
        print("BUSINESS_ID is required", file=sys.stderr)
        return 2
    if not args.map_url:
        print("MAP_URL is required", file=sys.stderr)
        return 2

    report_path = args.report or f"/tmp/partnership_smoke_{int(time.time())}.json"
    steps: list[StepResult] = []
    artifacts: dict[str, Any] = {
        "base_url": args.base_url,
        "business_id": args.business_id,
        "map_url": args.map_url,
        "lead_name": args.lead_name,
    }

    started_at = _utc_now()
    ok = True
    failure: str | None = None

    try:
        _run_step(
            steps,
            "import_links",
            lambda: _api_call(
                args.base_url,
                "/api/partnership/leads/import-links",
                args.token,
                method="POST",
                payload={"business_id": args.business_id, "links": [args.map_url]},
                timeout=args.timeout,
            ),
            fatal=False,
        )

        leads_data = _run_step(
            steps,
            "list_leads",
            lambda: _api_call(
                args.base_url,
                f"/api/partnership/leads?business_id={urllib.parse.quote(args.business_id)}",
                args.token,
                timeout=args.timeout,
            ),
        )
        items = leads_data.get("items") if isinstance(leads_data, dict) else []
        if not isinstance(items, list):
            items = []
        lead_id = _pick_lead_id(items, args.map_url)
        if not lead_id:
            raise SmokeFailure("lead_id not found after import/list")
        artifacts["lead_id"] = lead_id

        _run_step(
            steps,
            "parse_lead",
            lambda: _api_call(
                args.base_url,
                f"/api/partnership/leads/{urllib.parse.quote(lead_id)}/parse",
                args.token,
                method="POST",
                payload={"business_id": args.business_id},
                timeout=args.timeout,
            ),
            fatal=False,
        )

        _run_step(
            steps,
            "audit_lead",
            lambda: _api_call(
                args.base_url,
                f"/api/partnership/leads/{urllib.parse.quote(lead_id)}/audit",
                args.token,
                method="POST",
                payload={"business_id": args.business_id},
                timeout=args.timeout,
            ),
            fatal=False,
        )

        _run_step(
            steps,
            "match_lead",
            lambda: _api_call(
                args.base_url,
                f"/api/partnership/leads/{urllib.parse.quote(lead_id)}/match",
                args.token,
                method="POST",
                payload={"business_id": args.business_id},
                timeout=args.timeout,
            ),
            fatal=False,
        )

        _run_step(
            steps,
            "draft_offer",
            lambda: _api_call(
                args.base_url,
                f"/api/partnership/leads/{urllib.parse.quote(lead_id)}/draft-offer",
                args.token,
                method="POST",
                payload={"business_id": args.business_id, "channel": "telegram", "tone": "профессиональный"},
                timeout=args.timeout,
            ),
            fatal=False,
        )

        drafts_data = _run_step(
            steps,
            "list_drafts",
            lambda: _api_call(
                args.base_url,
                f"/api/partnership/drafts?business_id={urllib.parse.quote(args.business_id)}",
                args.token,
                timeout=args.timeout,
            ),
            fatal=False,
        )
        drafts = drafts_data.get("drafts") if isinstance(drafts_data, dict) else []
        if not isinstance(drafts, list):
            drafts = []
        draft_id = _pick_draft_id(drafts, lead_id)
        if draft_id:
            artifacts["draft_id"] = draft_id
            _run_step(
                steps,
                "approve_draft",
                lambda: _api_call(
                    args.base_url,
                    f"/api/partnership/drafts/{urllib.parse.quote(draft_id)}/approve",
                    args.token,
                    method="POST",
                    payload={"business_id": args.business_id, "approved_text": "smoke approve partnership draft"},
                    timeout=args.timeout,
                ),
                fatal=False,
            )

        create_batch_data = _run_step(
            steps,
            "create_batch",
            lambda: _api_call(
                args.base_url,
                "/api/partnership/send-batches",
                args.token,
                method="POST",
                payload={"business_id": args.business_id},
                timeout=args.timeout,
            ),
            fatal=False,
        )
        batch = create_batch_data.get("batch") if isinstance(create_batch_data, dict) else {}
        batch_id = str((batch or {}).get("id") or "").strip() or None

        snapshot_data = _run_step(
            steps,
            "list_batches",
            lambda: _api_call(
                args.base_url,
                f"/api/partnership/send-batches?business_id={urllib.parse.quote(args.business_id)}",
                args.token,
                timeout=args.timeout,
            ),
            fatal=False,
        )
        batches = snapshot_data.get("batches") if isinstance(snapshot_data, dict) else []
        if not isinstance(batches, list):
            batches = []
        if not batch_id:
            batch_id = _pick_batch_id(batches)
        if batch_id:
            artifacts["batch_id"] = batch_id
            _run_step(
                steps,
                "approve_batch",
                lambda: _api_call(
                    args.base_url,
                    f"/api/partnership/send-batches/{urllib.parse.quote(batch_id)}/approve",
                    args.token,
                    method="POST",
                    payload={"business_id": args.business_id},
                    timeout=args.timeout,
                ),
                fatal=False,
            )

        refreshed_batches_data = _run_step(
            steps,
            "list_batches_after_approve",
            lambda: _api_call(
                args.base_url,
                f"/api/partnership/send-batches?business_id={urllib.parse.quote(args.business_id)}",
                args.token,
                timeout=args.timeout,
            ),
            fatal=False,
        )
        refreshed_batches = refreshed_batches_data.get("batches") if isinstance(refreshed_batches_data, dict) else []
        if not isinstance(refreshed_batches, list):
            refreshed_batches = []

        queue_id = None
        if refreshed_batches:
            queue_id = _pick_queue_id(refreshed_batches[0])
        if queue_id:
            artifacts["queue_id"] = queue_id
            _run_step(
                steps,
                "record_outcome",
                lambda: _api_call(
                    args.base_url,
                    f"/api/partnership/send-queue/{urllib.parse.quote(queue_id)}/reaction",
                    args.token,
                    method="POST",
                    payload={"business_id": args.business_id, "outcome": "no_response"},
                    timeout=args.timeout,
                ),
                fatal=False,
            )

        _run_step(
            steps,
            "health",
            lambda: _api_call(
                args.base_url,
                f"/api/partnership/health?business_id={urllib.parse.quote(args.business_id)}",
                args.token,
                timeout=args.timeout,
            ),
            fatal=False,
        )
    except SmokeFailure as exc:
        ok = False
        failure = str(exc)

    finished_at = _utc_now()
    summary = {
        "started_at": started_at,
        "finished_at": finished_at,
        "ok": ok and all(step.ok for step in steps),
        "failure": failure,
        "artifacts": artifacts,
        "steps": [
            {
                "name": s.name,
                "ok": s.ok,
                "http_status": s.http_status,
                "detail": s.detail,
            }
            for s in steps
        ],
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"[smoke] report: {report_path}")
    for s in steps:
        print(f"- {s.name}: {'OK' if s.ok else 'FAIL'}"
              + (f" (HTTP {s.http_status})" if s.http_status is not None else "")
              + (f" :: {s.detail}" if s.detail else ""))
    if summary["ok"]:
        print("[smoke] partnership flow: PASS")
        return 0
    print(f"[smoke] partnership flow: FAIL :: {summary.get('failure') or 'step failures'}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
