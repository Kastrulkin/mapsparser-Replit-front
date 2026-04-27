#!/usr/bin/env python3
import subprocess
import sys


def run(cmd: list[str]) -> str:
    return subprocess.check_output(cmd, encoding="utf-8", stderr=subprocess.STDOUT).strip()


def check_git_status() -> None:
    print("1. Git status")
    try:
        msg = run(["git", "log", "-1", "--pretty=%B"])
        status = run(["git", "status", "--short"])
        print(f"   Last commit: {msg}")
        print(f"   Worktree: {'clean' if not status else 'dirty'}")
    except Exception as exc:
        print(f"   Error: {exc}")


def check_compose_runtime() -> None:
    print("\n2. Docker Compose runtime")
    try:
        output = run(["docker", "compose", "ps"])
        print(output)
    except Exception as exc:
        print(f"   Error: {exc}")


def check_frontend_dist() -> None:
    print("\n3. Frontend dist integrity")
    try:
        output = run(["bash", "scripts/verify_frontend_dist_integrity.sh", "frontend/dist"])
        print(output)
    except Exception as exc:
        print(f"   Error: {exc}")


def check_live_health() -> None:
    print("\n4. Backend health")
    try:
        output = run(["curl", "-I", "http://localhost:8000"])
        print(output)
    except Exception as exc:
        print(f"   Error: {exc}")


if __name__ == "__main__":
    print("Starting deployment verification for current Docker runtime\n")
    check_git_status()
    check_compose_runtime()
    check_frontend_dist()
    check_live_health()
    print("\nDone.")
