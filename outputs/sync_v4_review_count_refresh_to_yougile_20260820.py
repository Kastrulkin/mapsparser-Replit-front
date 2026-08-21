#!/usr/bin/env python3
"""Mirror verified review-count refresh sends to YouGile deal cards."""

from __future__ import annotations

import importlib.util
from pathlib import Path


BASE_PATH = Path(__file__).with_name("sync_v4_email_sends_to_yougile_20260820.py")
spec = importlib.util.spec_from_file_location("sync_v4_email_sends", BASE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
module.REMOTE_LOG = "debug_data/v4-review-count-refresh-live-20260820.log"
module.REMOTE_SESSION = "v4-review-count-refresh-20260820"


if __name__ == "__main__":
    module.main()
