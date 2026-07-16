#!/usr/bin/env python3
import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from database_manager import get_db_connection
from services.knowledge_ingestion import (
    BELESHKO_CHANNEL_KEY,
    BELESHKO_MESSAGE_ID,
    import_card_audits,
    import_services,
    import_telegram_archive,
    iter_telegram_archive,
    telegram_archive_dry_run,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Dry-run or import LocalOS knowledge corpora")
    parser.add_argument("--dataset", choices=["telegram", "services", "audits", "all"], default="all")
    parser.add_argument("--telegram-root", type=Path)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--analyze", action="store_true")
    parser.add_argument("--canary-size", type=int, default=105)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--report", type=Path)
    return parser


def _source_urls(path: Path | None) -> dict[str, str]:
    if not path or not path.exists():
        return {}
    result: dict[str, str] = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            folder = str(row.get("folder") or row.get("Папка экспорта") or "").strip()
            url = str(row.get("public_url") or row.get("Ссылка") or "").strip()
            if folder and url:
                result[folder] = url
    return result


def _canary_documents(root: Path, urls: dict[str, str], size: int) -> set[tuple[str, str]]:
    public_messages = [
        item for item in iter_telegram_archive(root)
        if item["channel_key"] in urls
    ]
    public_messages.sort(
        key=lambda item: (item["published_at"], len(item["content_text"])),
        reverse=True,
    )
    selected = {
        (item["channel_key"], item["external_id"])
        for item in public_messages[:max(1, size)]
    }
    selected.add((BELESHKO_CHANNEL_KEY, BELESHKO_MESSAGE_ID))
    return selected


def _db_counts(conn) -> dict[str, int]:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM userservices WHERE COALESCE(is_active, TRUE)")
        services = int(cursor.fetchone()[0])
        cursor.execute(
            """
            SELECT COUNT(*) FROM cards
            WHERE recommendations IS NOT NULL
              AND recommendations::text NOT IN ('null', '{}', '[]', '""')
            """
        )
        audits = int(cursor.fetchone()[0])
        return {"services": services, "audits": audits}
    finally:
        cursor.close()


def main() -> int:
    args = _parser().parse_args()
    report: dict[str, Any] = {"mode": "execute" if args.execute else "dry-run", "dataset": args.dataset}
    urls = _source_urls(args.source_manifest)

    if args.dataset in {"telegram", "all"}:
        if not args.telegram_root or not args.telegram_root.exists():
            raise SystemExit("--telegram-root is required for Telegram import")
        report["telegram"] = telegram_archive_dry_run(args.telegram_root, urls)

    conn = None
    if args.dataset in {"services", "audits", "all"} or args.execute:
        conn = get_db_connection()
    try:
        if conn and not args.execute:
            report["database"] = _db_counts(conn)
        if conn and args.execute:
            if args.dataset in {"telegram", "all"}:
                selected = _canary_documents(args.telegram_root, urls, args.canary_size) if args.analyze else set()
                report["telegram_import"] = import_telegram_archive(
                    conn,
                    root=args.telegram_root,
                    source_urls=urls,
                    analyze=args.analyze,
                    selected_documents=selected,
                    max_documents=args.limit,
                )
                conn.commit()
            if args.dataset in {"services", "all"}:
                report["services_import"] = import_services(conn, limit=args.limit)
                conn.commit()
            if args.dataset in {"audits", "all"}:
                report["audits_import"] = import_card_audits(conn, limit=args.limit)
                conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if conn:
            conn.close()

    output = json.dumps(report, ensure_ascii=False, indent=2, default=str)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
