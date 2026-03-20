#!/usr/bin/env python3
import argparse
import os
import random
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, List, Tuple


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from pg_db_utils import get_db_connection


TEST_URLS = (
    "https://geo.brdtest.com/welcome.txt?product=resi&method=native",
    "https://yandex.ru/maps/",
)


def _build_username(base_username: str, country_code: str) -> str:
    username = str(base_username or "").strip()
    if "brd-customer-" in username and "-session-" not in username:
        username = f"{username}-session-{int(datetime.now().timestamp())}{random.randint(100000, 999999)}"
    cc = str(country_code or "").strip().lower()
    if len(cc) == 2 and cc.isalpha() and f"-country-{cc}" not in username:
        username = f"{username}-country-{cc}"
    return username


def _curl_probe(host: str, port: int, username: str, password: str, url: str, max_time: int) -> Tuple[bool, float]:
    cmd = [
        "curl",
        "-sS",
        "-o",
        "/dev/null",
        "-w",
        "%{http_code}|%{time_total}",
        "--max-time",
        str(max_time),
        "--proxy",
        f"{host}:{port}",
        "--proxy-user",
        f"{username}:{password}",
        "-k",
        "-L",
        url,
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except Exception:
        return False, 999.0
    out = str(proc.stdout or "").strip()
    if "|" not in out:
        return False, 999.0
    code_raw, time_raw = out.split("|", 1)
    try:
        code = int(code_raw)
    except Exception:
        code = 0
    try:
        latency = float(time_raw)
    except Exception:
        latency = 999.0
    ok = 200 <= code < 400
    if code == 0:
        ok = False
    return ok, latency


def _health_score(success_count: int, failure_count: int) -> float:
    s = max(0, int(success_count or 0))
    f = max(0, int(failure_count or 0))
    return float(s + 1) / float(s + f + 2)


def _load_active_proxies(cur) -> List[Dict[str, Any]]:
    cur.execute(
        """
        SELECT
            id,
            host,
            port,
            username,
            password,
            COALESCE(success_count, 0) AS success_count,
            COALESCE(failure_count, 0) AS failure_count
        FROM proxyservers
        WHERE is_active = TRUE
        ORDER BY updated_at DESC NULLS LAST
        """
    )
    rows = cur.fetchall() or []
    out: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            proxy_id = row.get("id")
            host = row.get("host")
            port = row.get("port")
            username = row.get("username")
            password = row.get("password")
            success_count = row.get("success_count")
            failure_count = row.get("failure_count")
        else:
            proxy_id, host, port, username, password, success_count, failure_count = row
        out.append(
            {
                "id": str(proxy_id or "").strip(),
                "host": str(host or "").strip(),
                "port": int(port or 0),
                "username": str(username or "").strip(),
                "password": str(password or "").strip(),
                "success_count": int(success_count or 0),
                "failure_count": int(failure_count or 0),
            }
        )
    return out


def _update_proxy_state(cur, proxy_id: str, is_working: bool) -> None:
    cur.execute(
        """
        UPDATE proxyservers
        SET is_working = %s,
            last_checked_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (bool(is_working), str(proxy_id)),
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--country", default="", help="Optional 2-letter country code for BrightData username suffix")
    parser.add_argument("--org-url", default="https://yandex.ru/maps/org/186769473007/", help="Extra org URL probe")
    parser.add_argument("--max-time", type=int, default=18, help="curl max-time for probes")
    parser.add_argument("--pass-score", type=int, default=2, help="Minimum passed probes count to mark proxy working")
    args = parser.parse_args()

    urls = list(TEST_URLS) + [str(args.org_url or "").strip()]
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        proxies = _load_active_proxies(cur)
        if not proxies:
            print("[proxy-health] no active proxies")
            return

        print(f"[proxy-health] active_proxies={len(proxies)} probes={len(urls)}")
        for proxy in proxies:
            pid = proxy["id"]
            host = proxy["host"]
            port = proxy["port"]
            username = _build_username(proxy["username"], args.country)
            password = proxy["password"]
            pass_count = 0
            latencies: List[float] = []

            for url in urls:
                ok, latency = _curl_probe(host, port, username, password, url, args.max_time)
                if ok:
                    pass_count += 1
                latencies.append(latency)

            avg_latency = round(sum(latencies) / len(latencies), 3) if latencies else 999.0
            is_working = pass_count >= int(args.pass_score)
            prior_score = _health_score(proxy["success_count"], proxy["failure_count"])
            _update_proxy_state(cur, pid, is_working)
            print(
                "[proxy-health] "
                f"id={pid} pass={pass_count}/{len(urls)} avg={avg_latency}s "
                f"mark={'working' if is_working else 'down'} prior_score={prior_score:.3f}"
            )

        conn.commit()
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
